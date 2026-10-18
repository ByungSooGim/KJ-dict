"""
generate_dialect_prosody.py
===========================
경상도(경주어) 성조 및 고저장단 자동 후보정 음성 합성기 (2번 방식 프로토타입)

특징:
1. 표준형 고음질 Neural TTS(Edge TTS InJoon 남성 음성)로 자연스러운 원본 음성 생성
2. 사전의 성조 부호(′ 또는 ') 및 장모음(가아, 사알 등 모음 연타) 구문 분석
3. Praat PSOLA(Pitch Synchronous Overlap-Add) 음향 신호 처리:
   - 고음절('): 끝이 뚝 떨어지는 표준어 어미를 부드러운 코사인 S-Curve로 +5~6반음(약 50~70Hz) 상승
   - 장모음: DurationTier를 통해 모음 지속 시간을 1.5~1.7배 자연스럽게 연장
   - 완만한 음조 전이: 음절 간 급격한 계단식 꺾임 없이 경상도 사람의 자연스러운 억양 형성
4. 웹사전(index.html) 및 demo_prosody.html과 연동 지원
"""

import asyncio
import os
import re
import sys
import json
import numpy as np
import parselmouth
from parselmouth.praat import call
from pydub import AudioSegment
import edge_tts

VOICE_MALE = "ko-KR-InJoonNeural"
VOICE_FEMALE = "ko-KR-SunHiNeural"

TONE_MARKS_REGEX = re.compile(r"['′″ːˈˌ\^]")

def clean_for_tts(text: str) -> str:
    """TTS 합성용 텍스트 정제 (성조 부호 및 대괄호 제거)"""
    t = TONE_MARKS_REGEX.sub("", text)
    t = t.replace("[", "").replace("]", "").strip()
    return t

def parse_dialect_structure(text: str):
    """
    방언 표기에서 각 음절 단위의 성조(H/L)와 장모음(Long) 여부를 추출
    예:
      '가새′' -> [('가', 'L', False), ('새', 'H', False)]
      '가아′' -> [('가아', 'H', True)]
      '갈꾸리′' -> [('갈', 'L', False), ('꾸', 'L', False), ('리', 'H', False)]
      '보′또랑' -> [('보', 'H', False), ('또', 'L', False), ('랑', 'L', False)]
    """
    raw = text.replace("[", "").replace("]", "").strip()
    chars = list(raw)
    n = len(chars)
    
    raw_syllables = []
    idx = 0
    while idx < n:
        ch = chars[idx]
        if '가' <= ch <= '힣':
            # 다음 문자들 중 성조 부호 확인
            j = idx + 1
            has_tone = False
            while j < n and chars[j] in "'′″ːˈˌ^":
                has_tone = True
                j += 1
            raw_syllables.append({
                'char': ch,
                'tone': 'H' if has_tone else 'L'
            })
            idx = j
        else:
            idx += 1
            
    # 모음 중복(장모음) 병합 검사
    merged = []
    skip = False
    for i in range(len(raw_syllables)):
        if skip:
            skip = False
            continue
        cur = raw_syllables[i]
        if i + 1 < len(raw_syllables):
            nxt = raw_syllables[i+1]
            # nxt의 초성이 'ㅇ'인지 검사
            nxt_code = ord(nxt['char']) - 0xAC00
            nxt_cho = nxt_code // (21 * 28)
            if nxt_cho == 11: # 'ㅇ' 초성
                # 장모음으로 판정
                is_h = (cur['tone'] == 'H' or nxt['tone'] == 'H')
                merged.append({
                    'char': cur['char'] + nxt['char'],
                    'tone': 'H' if is_h else 'L',
                    'is_long': True
                })
                skip = True
                continue
        merged.append({
            'char': cur['char'],
            'tone': cur['tone'],
            'is_long': False
        })
        
    return merged

def get_speech_bounds(snd: parselmouth.Sound, threshold_db: float = 30.0):
    """오디오에서 앞뒤 무음 구간을 제외한 실제 발화 시작/종료 시간 측정"""
    intensity = snd.to_intensity()
    times = intensity.xs()
    values = intensity.values[0]
    
    max_val = np.max(values)
    valid_times = [t for t, v in zip(times, values) if v >= (max_val - threshold_db)]
    if not valid_times:
        return 0.05, max(0.1, snd.duration - 0.05)
    
    start_t = max(0.02, valid_times[0] - 0.03)
    end_t = min(snd.duration - 0.02, valid_times[-1] + 0.03)
    return start_t, end_t

def apply_prosody(wav_path: str, output_wav_path: str, syllable_info: list):
    """
    Praat PSOLA를 사용하여 피치(F0 Contour)와 음길이(DurationTier)를
    사투리 성조/장단에 맞게 보정
    """
    snd = parselmouth.Sound(wav_path)
    dur = snd.duration
    
    # 기본 Pitch 측정 (남성 음성 기본 75~400Hz 범위)
    pitch_obj = snd.to_pitch()
    f0_arr = pitch_obj.selected_array['frequency']
    valid_f0 = f0_arr[f0_arr > 0]
    
    if len(valid_f0) > 0:
        base_f0 = float(np.median(valid_f0))
    else:
        base_f0 = 125.0
        
    start_t, end_t = get_speech_bounds(snd)
    speech_dur = max(0.1, end_t - start_t)
    
    num_syls = len(syllable_info)
    if num_syls == 0:
        snd.save(output_wav_path, "WAV")
        return
        
    # 각 음절별 시간 가중치 계산 (장모음은 일반 음절의 1.6배 가중치)
    weights = [1.6 if s['is_long'] else 1.0 for s in syllable_info]
    total_weight = sum(weights)
    
    syl_durations = [(w / total_weight) * speech_dur for w in weights]
    
    syl_bounds = []
    curr = start_t
    for d in syl_durations:
        syl_bounds.append((curr, curr + d))
        curr += d
        
    # Praat Manipulation 객체 생성
    manipulation = call(snd, "To Manipulation", 0.01, 70, 450)
    pitch_tier = call(manipulation, "Extract pitch tier")
    duration_tier = call(manipulation, "Extract duration tier")
    
    # 성조 주파수 기준치 정의
    # L (저/평조): base_f0 * 0.95 ~ 1.0 (~120Hz)
    # H (고조): +5.5 반음 상승 (base_f0 * 1.37, ~170~180Hz)
    # 경상도 특유의 맛깔난 어미 고음 리프트(Ending Lift) 적용
    f_low = base_f0 * 0.95
    f_high = base_f0 * (2 ** (5.5 / 12))
    
    # 발화 구간 내 기존 피치 포인트 제거 후 새로운 S-Curve 피치 주입
    call(pitch_tier, "Remove points between", start_t, end_t)
    
    # 각 음절별 목표 F0 설정
    target_pitches = []
    for s in syllable_info:
        if s['tone'] == 'H':
            target_pitches.append(f_high)
        else:
            target_pitches.append(f_low)
            
    # 전체 시간에 걸쳐 부드러운 코사인 곡선(S-Curve)으로 연속 F0 궤적 계산
    time_points = []
    f0_points = []
    
    # 음절 중심 시점 및 목표 피치
    key_times = []
    key_pitches = []
    
    # 발화 시작점
    key_times.append(start_t)
    key_pitches.append(target_pitches[0] * 0.95)
    
    for idx, (b_start, b_end) in enumerate(syl_bounds):
        s_info = syllable_info[idx]
        b_mid = (b_start + b_end) / 2.0
        target_f = target_pitches[idx]
        
        # 만약 마지막 음절이 고조(H)인 경우:
        # 끝에서 떨어지지 않고, 음절 끝(b_end)까지 확실하게 치고 올라가는 상승조 형성!
        if idx == num_syls - 1 and s_info['tone'] == 'H':
            key_times.append(b_start + (b_end - b_start) * 0.2)
            key_pitches.append(f_low * 1.05)
            
            key_times.append(b_start + (b_end - b_start) * 0.8)
            key_pitches.append(f_high)
            
            key_times.append(b_end)
            key_pitches.append(f_high * 1.02)
        elif s_info['is_long']:
            # 장모음인 경우: 전반부는 부드럽게 유지하다가 후반부에 사투리 억양으로 올라가거나 안정
            key_times.append(b_start + (b_end - b_start) * 0.3)
            key_pitches.append(f_low if s_info['tone'] == 'L' else f_high * 0.92)
            
            key_times.append(b_start + (b_end - b_start) * 0.8)
            key_pitches.append(target_f)
        else:
            key_times.append(b_mid)
            key_pitches.append(target_f)
            
    # 완만한 곡선 포인트 주입 (10ms 간격으로 코사인 인터폴레이션)
    for k in range(len(key_times) - 1):
        t1, t2 = key_times[k], key_times[k+1]
        p1, p2 = key_pitches[k], key_pitches[k+1]
        steps = max(2, int((t2 - t1) / 0.015))
        for step in range(steps):
            frac = step / steps
            t = t1 + frac * (t2 - t1)
            # 코사인 보간 (S-Curve)
            smoothed_frac = 0.5 * (1 - np.cos(np.pi * frac))
            f = p1 + (p2 - p1) * smoothed_frac
            call(pitch_tier, "Add point", t, f)
            
    # 마지막 키포인트 추가
    call(pitch_tier, "Add point", key_times[-1], key_pitches[-1])
    
    # 장모음 음절이 있으면 DurationTier를 통해 길이 확장
    has_long_vowel = any(s['is_long'] for s in syllable_info)
    if has_long_vowel:
        for idx, (b_start, b_end) in enumerate(syl_bounds):
            if syllable_info[idx]['is_long']:
                b_mid = (b_start + b_end) / 2.0
                # 1.5배 연장
                call(duration_tier, "Add point", b_start, 1.0)
                call(duration_tier, "Add point", b_mid, 1.55)
                call(duration_tier, "Add point", b_end, 1.0)
        call([duration_tier, manipulation], "Replace duration tier")
        
    call([pitch_tier, manipulation], "Replace pitch tier")
    resynthesized = call(manipulation, "Get resynthesis (overlap-add)")
    resynthesized.save(output_wav_path, "WAV")


async def generate_prosody_sample(dialect_text: str, base_id: str, voice: str = VOICE_MALE):
    """
    표제어 또는 예문에 대해:
    1. 기본 TTS 원본 파일 생성 (audio/{base_id}_orig.mp3)
    2. 사투리 성조/장단 후보정 파일 생성 (audio/{base_id}_prosody.mp3)
    반환: (orig_path, prosody_path, syllables)
    """
    clean_text = clean_for_tts(dialect_text)
    syl_info = parse_dialect_structure(dialect_text)
    
    os.makedirs("audio", exist_ok=True)
    raw_mp3 = f"audio/{base_id}_orig.mp3"
    raw_wav = f"audio/{base_id}_temp.wav"
    out_wav = f"audio/{base_id}_prosody.wav"
    out_mp3 = f"audio/{base_id}_prosody.mp3"
    
    # 1. Edge-TTS 표준 합성
    comm = edge_tts.Communicate(clean_text, voice, rate="-3%")
    await comm.save(raw_mp3)
    
    # WAV 변환
    seg = AudioSegment.from_file(raw_mp3)
    seg.export(raw_wav, format="wav")
    
    # 2. Praat 기반 F0 & Duration 후보정
    apply_prosody(raw_wav, out_wav, syl_info)
    
    # MP3 변환
    seg_out = AudioSegment.from_file(out_wav)
    seg_out.export(out_mp3, format="mp3")
    
    # 임시 WAV 삭제
    for p in [raw_wav, out_wav]:
        if os.path.exists(p):
            try:
                os.remove(p)
            except:
                pass
                
    return raw_mp3, out_mp3, syl_info

async def build_prototype_showcase():
    """주요 경상도 억양 패턴별 대표 표제어 시제품 생성"""
    test_words = [
        ("가새′", "gasae", "가위 (말음절 고조 L-H)"),
        ("가아′", "gaa", "가다의 명령형 (장모음 연장 + 상승 고조 H)"),
        ("갈꾸리′", "galkkuri", "갈고리 (3음절 말음절 고조 L-L-H)"),
        ("보′또랑′", "bottorang", "보의 도랑 (첫음절/끝음절 복합 고조 H-L-H)"),
        ("초온′넘", "chonneom", "촌놈 (첫음절 장모음 연장 + 고조 H-L)"),
        ("모리′다′", "morida", "몰다 (연속 고조 L-H-H)"),
        ("웅′티이", "ungtii", "웅덩이 (고조 + 말음절 장모음 H-L)"),
    ]
    
    print("=" * 60)
    print("경상도(경주어) 성조 및 장단 자동 후보정 (2번 방식) 시제품 생성")
    print("=" * 60)
    
    results = []
    
    # 기존 audio_map.json 로드
    map_file = "audio/audio_map.json"
    audio_map = {}
    if os.path.exists(map_file):
        try:
            with open(map_file, "r", encoding="utf-8") as f:
                audio_map = json.load(f)
        except Exception as e:
            print(f"audio_map 로드 실패: {e}")
            
    for text, base_id, desc in test_words:
        print(f"\n[합성 중] {text} ({desc})")
        orig_mp3, prosody_mp3, syls = await generate_prosody_sample(text, base_id)
        print(f"  - 음절 분석: {syls}")
        print(f"  - 기본 TTS : {orig_mp3}")
        print(f"  - 사투리 후보정 : {prosody_mp3}")
        
        # audio_map.json에 등록하여 웹사전에서 바로 재생되도록 매핑
        audio_map[text] = prosody_mp3
        audio_map[f"[{text}]"] = prosody_mp3
        
        results.append({
            "text": text,
            "desc": desc,
            "syls": syls,
            "orig_mp3": orig_mp3,
            "prosody_mp3": prosody_mp3
        })
        
    # audio_map.json 저장
    with open(map_file, "w", encoding="utf-8") as f:
        json.dump(audio_map, f, ensure_ascii=False, indent=2)
    print(f"\n[완료] audio/audio_map.json에 {len(test_words)}개 표제어 등록 완료!")
    
    # 비교 청취용 데모 HTML 페이지 생성 (audio/demo_prosody.html)
    generate_demo_html(results)

def generate_demo_html(results):
    """비교 청취용 데모 웹페이지 생성"""
    items_html = ""
    for r in results:
        syl_chips = ""
        for s in r['syls']:
            badge_color = "#e53935" if s['tone'] == 'H' else "#757575"
            long_mark = " (장음)" if s['is_long'] else ""
            syl_chips += f"<span style='display:inline-block; padding:2px 8px; margin:2px; background:{badge_color}; color:#fff; border-radius:12px; font-size:12px;'>{s['char']}: {s['tone']}{long_mark}</span> "
            
        items_html += f"""
        <div style="background:#fff; border:1px solid #ddd; border-radius:12px; padding:16px; margin-bottom:16px; box-shadow:0 2px 5px rgba(0,0,0,0.05);">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <div>
                    <span style="font-size:24px; font-weight:bold; color:#1a237e;">{r['text']}</span>
                    <span style="color:#666; font-size:14px; margin-left:10px;">{r['desc']}</span>
                </div>
                <div>{syl_chips}</div>
            </div>
            
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:12px;">
                <div style="background:#f5f5f5; border-radius:8px; padding:12px;">
                    <div style="font-weight:bold; color:#555; margin-bottom:6px; font-size:13px;">1. 표준 Neural TTS (기본형)</div>
                    <audio controls style="width:100%; height:36px;">
                        <source src="{r['orig_mp3'].replace('audio/', '')}" type="audio/mpeg">
                    </audio>
                    <div style="font-size:11px; color:#888; margin-top:4px;">* 어미가 아래로 뚝 떨어지는 표준어 억양</div>
                </div>
                
                <div style="background:#e8f4fd; border:1px solid #90caf9; border-radius:8px; padding:12px;">
                    <div style="font-weight:bold; color:#1976d2; margin-bottom:6px; font-size:13px;">2. 2번 방식: 경상도 성조/장단 후보정 (시제품)</div>
                    <audio controls style="width:100%; height:36px;">
                        <source src="{r['prosody_mp3'].replace('audio/', '')}" type="audio/mpeg">
                    </audio>
                    <div style="font-size:11px; color:#1565c0; margin-top:4px;">* F0 곡선 상승 + 장모음 1.6배 연장 (자연스러운 경상도 억양)</div>
                </div>
            </div>
        </div>
        """
        
    html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>경상도(경주어) 성조 및 고저장단 후보정 (2번 방식) 시제품 청취실</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Malgun Gothic", sans-serif;
            background: #f0f2f5;
            margin: 0;
            padding: 24px;
            color: #333;
        }}
        .container {{
            max-width: 860px;
            margin: 0 auto;
        }}
        .header {{
            background: linear-gradient(135deg, #1976d2, #0d47a1);
            color: white;
            padding: 24px;
            border-radius: 16px;
            margin-bottom: 24px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        .badge {{
            background: rgba(255,255,255,0.2);
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 13px;
            font-weight: normal;
        }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1 style="margin:0 0 8px 0; font-size:24px;">경상도(경주어) 사투리 성조/장단 음향 후보정 시제품</h1>
        <div style="font-size:14px; opacity:0.9; line-height:1.6;">
            사전의 성조 부호(′) 및 모음 연타(장모음)를 Praat PSOLA 신호 처리로 자동 변환한 결과입니다.<br>
            표준 TTS의 하강 억양과 사투리 후보정 음성을 직접 비교해서 들어보실 수 있습니다.
        </div>
    </div>
    
    {items_html}
    
    <div style="text-align:center; margin-top:30px; color:#666; font-size:13px;">
        경주어사전 웹사전 연동 완료 | 2번 방식: Edge-TTS InJoon + Praat F0/Duration Resynthesis
    </div>
</div>
</body>
</html>
"""
    with open("audio/demo_prosody.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    
    # 루트 디렉토리에도 demo_prosody.html 생성 (audio/ 상대경로 적용)
    root_html = html_content
    for r in results:
        root_html = root_html.replace(f'src="{r["orig_mp3"].replace("audio/", "")}"', f'src="{r["orig_mp3"]}"')
        root_html = root_html.replace(f'src="{r["prosody_mp3"].replace("audio/", "")}"', f'src="{r["prosody_mp3"]}"')
    with open("demo_prosody.html", "w", encoding="utf-8") as f:
        f.write(root_html)
    print("  - 비교 청취 데모 페이지 생성 완료: demo_prosody.html 및 audio/demo_prosody.html")

if __name__ == "__main__":
    asyncio.run(build_prototype_showcase())
