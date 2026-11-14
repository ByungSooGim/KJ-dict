import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import re
import edge_tts

from generate_dialect_prosody import synthesize_memory_mp3

PORT = int(os.environ.get('PORT', 5050))

class EdgeTTSHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "engine": "Edge-TTS + Praat PSOLA In-Memory"}).encode('utf-8'))

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            req = json.loads(post_data.decode('utf-8'))
            text = req.get('text', '')
            mode = req.get('mode', 'prosody')  # 'orig' or 'prosody'
            voice = req.get('voice', 'ko-KR-InJoonNeural')
            semitone_lift = float(req.get('semitone_lift', 5.5))
            long_stretch = float(req.get('long_stretch', 1.55))

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            audio_data = loop.run_until_complete(
                synthesize_memory_mp3(
                    dialect_text=text,
                    mode=mode,
                    voice=voice,
                    semitone_lift=semitone_lift,
                    long_stretch=long_stretch
                )
            )
            loop.close()

            self.send_response(200)
            self.send_header('Content-Type', 'audio/mpeg')
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
        pass

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', PORT), EdgeTTSHandler)
    print(f"Gyeongju Dialect Real-Time Prosody Server running on http://localhost:{PORT} (Zero disk MP3s)")
    server.serve_forever()
