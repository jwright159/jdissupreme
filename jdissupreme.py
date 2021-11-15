from typing import Any, Callable
import aiohttp, asyncio, zlib, sys, enum, json

from aiohttp.client_ws import ClientWebSocketResponse

ZLIB_SUFFIX = b'\x00\x00\xff\xff'
buffer = bytearray()
inflator = zlib.decompressobj()

def on_websocket_message(msg: bytes):
	global buffer
	buffer.extend(msg)

	if len(msg) < 4 or msg[-4:] != ZLIB_SUFFIX:
		return

	msg = inflator.decompress(buffer)
	buffer = bytearray()

	# here you can treat `msg` as either JSON or ETF encoded,
	# depending on your `encoding` param


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

Event = Callable[[dict[str, Any]], None]

class Client():
	def __init__(self):
		self.events: dict[str, list[Event]] = {}
		self.sequence_id = None
	
	def on(self, event_name: str) -> Callable[[Event], Event]:
		if event_name not in self.events:
			self.events[event_name] = []
		def wrapperer(event: Event) -> Event:
			self.events[event_name].append(event)
			return event
		return wrapperer

	async def connect(self, token: str, activity_name: str, activity_type: int):
		loop = asyncio.get_event_loop()
		async with aiohttp.ClientSession() as session:
			async with session.ws_connect('wss://gateway.discord.gg/?v=9&encoding=json&compress=zlib-stream') as websocket:
				ZLIB_SUFFIX = b'\x00\x00\xff\xff'
				buffer = bytearray()
				inflator = zlib.decompressobj()

				async for msg in websocket:
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
							await websocket.send_json({
								'op': Opcode.IDENTIFY.value,
								'd': {
									'token': token,
									'properties': {
										'$os': sys.platform,
										'$device': 'jdissupreme',
										'$browser': 'jdissupreme',
									},
									'compress': True,
									'presence': {
										'activities': [{
											'name': activity_name,
											'type': activity_type,
										}],
										'status': 'online',
										'afk': False,
									},
									'intents': 0b111_1110_0000_0000,
								},
							})
							asyncio.ensure_future(self.heartbeat(websocket, int(data['heartbeat_interval'])), loop=loop)
						
						case Opcode.DISPATCH:
							print("Dispatched", event_name, json.dumps(data, indent=4))
							assert data is not None
							assert event_name is not None
							if event_name in self.events:
								for event in self.events[event_name]:
									event(data)
						
						case Opcode.HEARTBEAT_ACK:
							print("Heartbeat ack")
	
	async def heartbeat(self, websocket: ClientWebSocketResponse, interval: int):
		while True:
			beat = {
				'op': Opcode.HEARTBEAT.value,
				'd': self.sequence_id,
			}
			await websocket.send_str(json.dumps(beat))
			print("Heartbeat", beat)
			await asyncio.sleep(interval / 1000)

if __name__ == '__main__':
	client = Client()

	@client.on('MESSAGE_CREATE')
	def message(data: dict[str, Any]):
		print('Messaged from', data['author']['username'], 'aka', data['member']['nick'], 'for', data['content'])

	with open('token.txt') as token_file:
		token = token_file.read()
	asyncio.run(client.connect(token, 'jdissupreme', 0))

	"""async with session.get('https://discord.com/api/v9',
		headers={
			'User-Agent': 'DiscordBot (https://github.com/jwright159/jdissupreme 1.0)',
			'Authorization': 'wouldn't you like to know? ;)'
		},
	) as res:
		print(await res.json())"""