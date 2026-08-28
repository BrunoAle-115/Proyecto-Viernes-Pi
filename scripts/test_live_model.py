import os, asyncio, json, websockets
from dotenv import load_dotenv

load_dotenv('/home/bruno/viernes/V.I.E.R.N.E.S/.env')
key = os.getenv('GEMINI_API_KEY')

async def test_model(model_name):
    url = f'wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent?key={key}'
    try:
        async with websockets.connect(url, ping_interval=10, ping_timeout=10) as ws:
            setup = {
                'setup': {
                    'model': model_name,
                    'generationConfig': {
                        'responseModalities': ['AUDIO'],
                        'speechConfig': {
                            'voiceConfig': {
                                'prebuiltVoiceConfig': {
                                    'voiceName': 'Aoede'
                                }
                            }
                        }
                    }
                }
            }
            await ws.send(json.dumps(setup))
            msg = await ws.recv()
            print(f'RESULT [{model_name}]:', msg[:150])
    except Exception as e:
        print(f'ERROR [{model_name}]:', e)

async def main():
    for m in ['models/gemini-2.0-flash-exp', 'models/gemini-2.0-flash-realtime-exp', 'models/gemini-2.5-flash-native-audio-latest']:
        await test_model(m)

if __name__ == '__main__':
    asyncio.run(main())
