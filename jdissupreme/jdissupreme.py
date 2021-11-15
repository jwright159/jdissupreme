from functools import wraps
from typing import Any, Callable, Coroutine, ParamSpec, TypeVar
import aiohttp, asyncio, zlib, sys, enum, json

P = ParamSpec('P')
T = TypeVar('T')
def main(f: Callable[P, T]) -> Callable[P, T]:
	@wraps(f)
	def wrapper(*args: P.args, **kwargs: P.kwargs):
		if __name__ == '__main__':
			f(*args, **kwargs)
	return wrapper
print = main(print)

class Opcode(enum.Enum):
	DISPATCH		= 0	 #	Dispatch				Receive			An event was dispatched.
	HEARTBEAT		= 1	 #	Heartbeat				Send/Receive	Fired periodically by the client to keep the connection alive.
	IDENTIFY		= 2	 #	Identify				Send			Starts a new session during the initial handshake.
	PRESENCE		= 3	 #	Presence Update			Send			Update the client's presence.
	VOICE			= 4	 #	Voice State Update		Send			Used to join/leave or move between voice channels.
	RESUME			= 6	 #	Resume					Send			Resume a previous session that was disconnected.
	RECONNECT		= 7	 #	Reconnect				Receive			You should attempt to reconnect and resume immediately.
	REQUEST			= 8	 #	Request Guild Members	Send			Request information about offline guild members in a large guild.
	INVALID			= 9	 #	Invalid Session			Receive			The session has been invalidated. You should reconnect and identify/resume accordingly.
	HELLO			= 10 #	Hello					Receive			Sent immediately after connecting, contains the heartbeat_interval to use.
	HEARTBEAT_ACK	= 11 #	Heartbeat ACK			Receive			Sent in response to receiving a heartbeat to acknowledge that it has been received.

Event = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]

class Client:
	def __init__(self, token: str, activity_name: str, activity_type: int):
		self.token = token
		self.activity_name = activity_name
		self.activity_type = activity_type
		self.events: dict[str, list[Event]] = {}
		self.sequence_id = None
		self._dm_channels: dict[str, str] = {}

		self.on('READY')(self._on_ready)
	
	def on(self, event_name: str) -> Callable[[Event], Event]:
		if event_name not in self.events:
			self.events[event_name] = []
		def wrapperer(event: Event) -> Event:
			self.events[event_name].append(event)
			return event
		return wrapperer

	async def connect(self) -> None:
		loop = asyncio.get_event_loop()
		async with aiohttp.ClientSession(
			headers={
				'User-Agent': 'DiscordBot (https://github.com/jwright159/jdissupreme 1.0)',
				'Authorization': 'Bot ' + self.token,
			},
			raise_for_status=True,
		) as self.session:
			async with self.session.ws_connect('wss://gateway.discord.gg/?v=9&encoding=json&compress=zlib-stream') as self.websocket:
				ZLIB_SUFFIX = b'\x00\x00\xff\xff'
				buffer = bytearray()
				inflator = zlib.decompressobj()

				async for msg in self.websocket:
					msg_bytes: bytes = msg.data # type: ignore
					buffer.extend(msg_bytes)

					if len(msg_bytes) < 4 or msg_bytes[-4:] != ZLIB_SUFFIX:
						continue

					jstr = inflator.decompress(buffer)
					buffer = bytearray()

					js = json.loads(jstr)

					opcode = Opcode(int(js['op']))
					data = js['d'] if 'd' in js else None
					event_name = str(js['t']) if js['t'] else None
					if js['s']:
						self.sequence_id = int(js['s'])

					match opcode:
						case Opcode.HELLO:
							assert data is not None
							await self.websocket.send_json({
								'op': Opcode.IDENTIFY.value,
								'd': {
									'token': self.token,
									'properties': {
										'$os': sys.platform,
										'$device': 'jdissupreme',
										'$browser': 'jdissupreme',
									},
									'compress': True,
									'presence': {
										'activities': [{
											'name': self.activity_name,
											'type': self.activity_type,
										}],
										'status': 'online',
										'afk': False,
									},
									'intents': 0b111_1110_0000_0000,
								},
							})
							asyncio.ensure_future(self._heartbeat(int(data['heartbeat_interval'])), loop=loop)
						
						case Opcode.DISPATCH:
							print("Dispatched", event_name, json.dumps(data, indent=4))
							assert data is not None
							assert event_name is not None
							if event_name in self.events:
								for event in self.events[event_name]:
									await event(data)
						
						case Opcode.HEARTBEAT_ACK:
							print("Heartbeat ack")

	async def _on_ready(self, data: dict[str, Any]):
		self.me: dict[str, Any] = data['user']
	
	async def _heartbeat(self, interval: int):
		while True:
			beat = {
				'op': Opcode.HEARTBEAT.value,
				'd': self.sequence_id,
			}
			await self.websocket.send_str(json.dumps(beat))
			print("Heartbeat", beat)
			await asyncio.sleep(interval / 1000)

	async def _request(self, method: str, endpoint: str, data: Any = None) -> dict[str, Any]:
		async with self.session.request(method, 'https://discord.com/api/v9' + endpoint, data=data) as res:
			data = await res.json()
			print("Requested", data)
			if 'x-ratelimit-remaining' in res.headers:
				print(f"{res.headers['x-ratelimit-remaining']} requests remaining, resetting in {res.headers['x-ratelimit-reset-after']} seconds")
				if res.headers['x-ratelimit-remaining'] == '0':
					print("Rate limiting for", res.headers['x-ratelimit-reset-after'], "seconds")
					await asyncio.sleep(float(res.headers['x-ratelimit-reset-after']))
			return data

	async def send(self, text: str, *, channel: str) -> None:
		await self._request('POST', f'/channels/{channel}/messages', {
			'content': text,
		})
	
	async def get_dm_channel(self, user: str) -> str:
		if user not in self._dm_channels:
			data = await self._request('POST', f'/users/@me/channels', {
				'recipient_id': user,
			})
			self._dm_channels[user] = str(data['id'])
		return self._dm_channels[user]
	
	async def get_user(self, user: str) -> dict[str, Any]:
		return await self._request('POST', f'/users/{user}')
	
	async def get_me(self, user: str) -> dict[str, Any]:
		self.me: dict[str, Any] = await self._request('POST', f'/users/@me')
		return self.me

if __name__ == '__main__':
	with open('token.txt') as token_file:
		t = token_file.read()
	client = Client(t, 'jdissupreme', 0)

	@client.on('READY')
	async def on_ready(data: dict[str, Any]):
		print("Ready")

	@client.on('MESSAGE_CREATE')
	async def message(data: dict[str, Any]):
		print(f"Messaged from {data['author']['username']}{' aka ' + data['member']['nick'] if 'guild_id' in data else ''} for {data['content']}")
		contents = str(data['content']).split()
		match contents[0].lower():
			case 'ping':
				if len(contents) > 1:
					for i in range(int(contents[1])):
						await client.send(f"pong {i+1}", channel=data['channel_id'])
				else:
					await client.send("pong", channel=data['channel_id'])
			#case 'list':
			#	await client._request('GET', '/users/@me/channels')
			#	await client.send("Printed to console", channel=data['channel_id'])
	
	asyncio.run(client.connect())