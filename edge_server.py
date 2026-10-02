import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import edge_tts
import io

PORT = 5050

class EdgeTTSHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        # CORS Preflight 허용
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            req = json.loads(post_data.decode('utf-8'))
            ssml = req.get('ssml', '')
            text = req.get('text', '')
            voice = req.get('voice', 'ko-KR-InJoonNeural')

            async def generate_audio():
                if ssml:
                    # SSML이 제공된 경우 Communicate에 직접 전달
                    communicate = edge_tts.Communicate(text=ssml, voice=voice)
                else:
                    communicate = edge_tts.Communicate(text=text, voice=voice)
                
                audio_bytes = bytearray()
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_bytes.extend(chunk["data"])
                return audio_bytes

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            audio_data = loop.run_until_complete(generate_audio())
            loop.close()

            self.send_response(200)
            self.send_header('Content-Type', 'audio/mp3')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', str(len(audio_data)))
            self.end_headers()
            self.wfile.write(audio_data)

        except Exception as e:
            err_msg = json.dumps({'error': str(e)}).encode('utf-8')
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(err_msg)

    def log_message(self, format, *args):
        # 콘솔 로그 간소화
        pass

if __name__ == '__main__':
    server = HTTPServer(('127.0.0.1', PORT), EdgeTTSHandler)
    print(f"Edge TTS Proxy Server running on http://127.0.0.1:{PORT}")
    server.serve_forever()
