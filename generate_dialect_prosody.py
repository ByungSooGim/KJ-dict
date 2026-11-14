"""
generate_dialect_prosody.py
===========================
경상도(경주어) 문장 단위 성조 및 고저장단 실시간 음향 후보정 엔진 (2번 방식)
- 디스크에 MP3 파일을 미리 쌓아두지 않고, 요청 시 메모리(임시 버퍼)에서 즉시 합성 후 바이트 반환 지원
- Edge-TTS WordBoundary(어절 타임스탬프) + Praat PSOLA(F0 S-Curve & DurationTier) 결합
"""

import asyncio
import io
import os
import re
import tempfile
import numpy as np
import parselmouth
from parselmouth.praat import call
from pydub import AudioSegment
import edge_tts

VOICE_MALE = "ko-KR-InJoonNeural"
VOICE_FEMALE = "ko-KR-SunHiNeural"

TONE_MARKS_REGEX = re.compile(r"['′″ːˈˌ\^]")

def clean_for_tts(text: str) -> str:
    """TTS 합성용 평문 추출"""
    t = text.strip()
    if t.startswith('[') and t.endswith(']'):
        t = t[1:-1].strip()
    t = re.sub(r'\{([^/>-]+)[/>-][^}]+\}', r'\1', t)
    t = re.sub(r'<[^>]+>', '', t)
    t = t.replace('°', '')
    t = TONE_MARKS_REGEX.sub("", t)
    return re.sub(r'\s+', ' ', t).strip()

def parse_word_syllables(word_dialect: str):
    """
    단일 어절에서 음절별 성조(H/L)와 장모음(모음 2개 연달아 쓴 경우) 분석
    예: '사아′라′미' -> [{'char': '사아', 'tone': 'H', 'is_long': True}, {'char': '라', 'tone': 'H', 'is_long': False}, {'char': '미', 'tone': 'L', 'is_long': False}]
    """
    raw = word_dialect.strip()
    chars = list(raw)
    n = len(chars)
    
    raw_syllables = []
    idx = 0
    while idx < n:
        ch = chars[idx]
        if '가' <= ch <= '힣':
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
            
    # 모음 중복(장모음) 병합: 뒷글자 초성이 'ㅇ'(11)이고 모음 계열이 이어질 때
    merged = []
    skip = False
    for i in range(len(raw_syllables)):
        if skip:
            skip = False
            continue
        cur = raw_syllables[i]
        if i + 1 < len(raw_syllables):
            nxt = raw_syllables[i + 1]
            cur_code = ord(cur['char']) - 0xAC00
            nxt_code = ord(nxt['char']) - 0xAC00
            cur_jung = (cur_code // 28) % 21
            cur_jong = cur_code % 28
            nxt_cho = nxt_code // (21 * 28)
            nxt_jung = (nxt_code // 28) % 21
            
            # 앞 글자에 받침이 없고, 뒷 글자 초성이 'ㅇ'이며 동일/유사 모음 연타인 경우 (예: 가아, 사아, 해애, 초온, 서어, 지일, 타아)
            if cur_jong == 0 and nxt_cho == 11 and (cur_jung == nxt_jung or (cur_jung in (0,1,4,5,8,13,18,20) and nxt_jung == cur_jung)):
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

def tokenize_dialect_words(sentence: str):
    """문장을 어절 단위로 분리하여 각 어절의 평문과 방언 음절 정보 리스트 반환"""
    t = sentence.strip()
    if t.startswith('[') and t.endswith(']'):
        t = t[1:-1].strip()
    t = re.sub(r'\{([^/>-]+)[/>-][^}]+\}', r'\1', t)
    t = re.sub(r'<[^>]+>', '', t)
    t = t.replace('°', '')
    
    raw_words = [w for w in re.split(r'\s+', t) if w]
    result = []
    for rw in raw_words:
        clean_w = re.sub(r"[^가-힣]", "", TONE_MARKS_REGEX.sub("", rw))
        syls = parse_word_syllables(rw)
        if clean_w and syls:
            result.append({
                'raw': rw,
                'clean': clean_w,
                'syls': syls
            })
    return result

def apply_sentence_prosody(wav_path: str, out_wav_path: str, dialect_words: list, word_boundaries: list, semitone_lift: float = 5.5, long_stretch: float = 1.55):
    """
    문장 전체 오디오에 대해 어절 경계(WordBoundary)를 기준으로
    Praat PSOLA F0 S-Curve(고저) 및 DurationTier(장모음 늘림) 적용
    """
    snd = parselmouth.Sound(wav_path)
    dur = snd.duration
    
    pitch_obj = snd.to_pitch()
    f0_arr = pitch_obj.selected_array['frequency']
    valid_f0 = f0_arr[f0_arr > 0]
    base_f0 = float(np.median(valid_f0)) if len(valid_f0) > 0 else 125.0
    
    f_low = base_f0 * 0.93
    f_high = base_f0 * (2 ** (semitone_lift / 12.0))
    
    manipulation = call(snd, "To Manipulation", 0.01, 70, 450)
    pitch_tier = call(manipulation, "Extract pitch tier")
    duration_tier = call(manipulation, "Extract duration tier")
    
    # WordBoundary 매칭: 만약 WordBoundary가 비어있으면 전체 발화 구간을 어절 글자수 비례로 분할
    if not word_boundaries or len(word_boundaries) != len(dialect_words):
        intensity = snd.to_intensity()
        times = intensity.xs()
        vals = intensity.values[0]
        max_v = np.max(vals)
        valid_t = [t for t, v in zip(times, vals) if v >= max_v - 30.0]
        s_start = max(0.03, valid_t[0] - 0.02) if valid_t else 0.05
        s_end = min(dur - 0.03, valid_t[-1] + 0.02) if valid_t else max(0.1, dur - 0.05)
        total_span = max(0.2, s_end - s_start)
        
        weights = [sum(1.5 if s['is_long'] else 1.0 for s in w['syls']) for w in dialect_words]
        tot_w = sum(weights) if sum(weights) > 0 else 1.0
        
        word_boundaries = []
        cur_t = s_start
        for w_weight in weights:
            w_dur = (w_weight / tot_w) * total_span
            word_boundaries.append((cur_t, cur_t + w_dur))
            cur_t += w_dur

    has_any_long = False
    
    for w_info, (w_start, w_end) in zip(dialect_words, word_boundaries):
        w_start = max(0.01, min(dur - 0.05, w_start))
        w_end = max(w_start + 0.04, min(dur - 0.01, w_end))
        w_dur = w_end - w_start
        
        syls = w_info['syls']
        if not syls:
            continue
            
        # 어절 내에 고조(H)나 장모음이 하나라도 있을 때만 집중 보정 (자연스러운 억양 유지)
        has_h = any(s['tone'] == 'H' for s in syls)
        has_long = any(s['is_long'] for s in syls)
        if not has_h and not has_long:
            continue
            
        s_weights = [long_stretch if s['is_long'] else 1.0 for s in syls]
        tot_sw = sum(s_weights)
        s_durs = [(sw / tot_sw) * w_dur for sw in s_weights]
        
        s_bounds = []
        c_t = w_start
        for sd in s_durs:
            s_bounds.append((c_t, c_t + sd))
            c_t += sd
            
        call(pitch_tier, "Remove points between", w_start, w_end)
        
        key_times = [w_start]
        key_pitches = [f_high * 0.92 if syls[0]['tone'] == 'H' else f_low]
        
        for idx, (b_start, b_end) in enumerate(s_bounds):
            s = syls[idx]
            b_mid = (b_start + b_end) / 2.0
            target_f = f_high if s['tone'] == 'H' else f_low
            
            # 어절 마지막 음절이 고조(H)인 경우: 끝이 떨어지지 않고 부드럽게 상승 유지
            if idx == len(syls) - 1 and s['tone'] == 'H':
                key_times.append(b_start + (b_end - b_start) * 0.25)
                key_pitches.append(f_low * 1.05 if idx > 0 and syls[idx-1]['tone'] == 'L' else f_high * 0.95)
                key_times.append(b_start + (b_end - b_start) * 0.85)
                key_pitches.append(f_high * 1.03)
                key_times.append(b_end)
                key_pitches.append(f_high)
            elif s['is_long']:
                # 장모음: 앞쪽에서 시작하여 목표 성조로 부드럽게 글라이드
                key_times.append(b_start + (b_end - b_start) * 0.25)
                key_pitches.append(f_low * 1.04 if s['tone'] == 'H' else f_low)
                key_times.append(b_start + (b_end - b_start) * 0.80)
                key_pitches.append(target_f)
            else:
                key_times.append(b_mid)
                key_pitches.append(target_f)
                
            if s['is_long']:
                has_any_long = True
                call(duration_tier, "Add point", max(0.001, b_start - 0.01), 1.0)
                call(duration_tier, "Add point", b_mid, long_stretch)
                call(duration_tier, "Add point", min(dur - 0.001, b_end + 0.01), 1.0)
                
        # 코사인 S-Curve 보간으로 계단 현상 없는 매끄러운 F0 곡선 생성
        for k in range(len(key_times) - 1):
            t1, t2 = key_times[k], key_times[k+1]
            p1, p2 = key_pitches[k], key_pitches[k+1]
            if t2 <= t1:
                continue
            steps = max(2, int((t2 - t1) / 0.015))
            for step in range(steps):
                frac = step / steps
                t = t1 + frac * (t2 - t1)
                smoothed = 0.5 * (1.0 - np.cos(np.pi * frac))
                f = p1 + (p2 - p1) * smoothed
                call(pitch_tier, "Add point", t, f)
        call(pitch_tier, "Add point", key_times[-1], key_pitches[-1])
        
    if has_any_long:
        call([duration_tier, manipulation], "Replace duration tier")
    call([pitch_tier, manipulation], "Replace pitch tier")
    
    resynthesized = call(manipulation, "Get resynthesis (overlap-add)")
    resynthesized.save(out_wav_path, "WAV")

async def synthesize_memory_mp3(dialect_text: str, mode: str = "prosody", voice: str = VOICE_MALE, semitone_lift: float = 5.5, long_stretch: float = 1.55) -> bytes:
    """
    디스크에 영구 MP3를 남기지 않고 즉석에서 합성하여 MP3 bytes를 반환
    mode:
      - 'orig': 표준 평문 TTS
      - 'prosody': 2번 방식 (경상도 성조 S-Curve + 장모음 늘림 후보정)
    """
    clean_text = clean_for_tts(dialect_text)
    comm = edge_tts.Communicate(clean_text, voice, rate="-4%", boundary="WordBoundary")
    
    audio_bytes = bytearray()
    word_boundaries = []
    
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            audio_bytes.extend(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            offset_sec = chunk["offset"] / 1e7
            dur_sec = chunk["duration"] / 1e7
            word_boundaries.append((offset_sec, offset_sec + dur_sec))
            
    if mode == "orig":
        return bytes(audio_bytes)
        
    dialect_words = tokenize_dialect_words(dialect_text)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_mp3 = os.path.join(tmpdir, "in.mp3")
        raw_wav = os.path.join(tmpdir, "in.wav")
        out_wav = os.path.join(tmpdir, "out.wav")
        out_mp3 = os.path.join(tmpdir, "out.mp3")
        
        with open(raw_mp3, "wb") as f:
            f.write(audio_bytes)
            
        seg = AudioSegment.from_file(raw_mp3)
        seg.export(raw_wav, format="wav")
        
        apply_sentence_prosody(raw_wav, out_wav, dialect_words, word_boundaries, semitone_lift, long_stretch)
        
        seg_out = AudioSegment.from_file(out_wav)
        seg_out.export(out_mp3, format="mp3")
        
        with open(out_mp3, "rb") as f:
            return f.read()
