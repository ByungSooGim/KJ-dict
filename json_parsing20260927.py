import re
import json
import gzip
import base64
import math

# 한양 PUA(U+E000..U+F8FF) -> 표준 유니코드 첫가끝 조합형 자모 변환표
PUA_TO_UNICODE = {
    "": "거ᇹ",  # 거ᇹ
    "": "구ᇬ",  # 구ᇬ
    "": "나ᇬ",  # 나ᇬ
    "": "녀ᇅ",  # 녀ᇅ
    "": "도ᇘ",  # 도ᇘ
    "": "루ᇹ",  # 루ᇹ
    "": "리ᇹ",  # 리ᇹ
    "": "모ᇙ",  # 모ᇙ
    "": "부ᇯ",  # 부ᇯ
    "": "부ᇹ",  # 부ᇹ
    "": "사ᇙ",  # 사ᇙ
    "": "수ᇹ",  # 수ᇹ
    "": "시ᇙ",  # 시ᇙ
    "": "시ᇡ",  # 시ᇡ
    "": "어ᇝ",  # 어ᇝ
    "": "으ᇙ",  # 으ᇙ
    "": "이ᇙ",  # 이ᇙ
    "": "ᄋᆡ",        # ᄋᆡ
    "": "ᅌᅳ",        # ᅌᅳ
    "": "주ᇹ",  # 주ᇹ
    "": "쪼ᇹ",  # 쪼ᇹ
    "": "커ᇹ",  # 커ᇹ
    "": "ᄒᆞ",        # ᄒᆞ
    "": "ᄂ",              # ᄂ
    "": "ᄉ",              # ᄉ
    "": "ᄋ",              # ᄋ
    "": "ᄌ",              # ᄌ
    "": "ᅡ",              # ᅡ
    "": "ᅧ",              # ᅧ
    "": "ᆖ",              # ᆖ
    "": "ᆫ",              # ᆫ
    "": "ퟶ",              # ퟶ
}
_PUA_PATTERN = re.compile("|".join(map(re.escape, PUA_TO_UNICODE)))


def correct_dialect_typos(text):
    """사전 원문 내 오탈자 교정:
    - '왕임ㅎ다' 축약형에서 '아래아+이'(ᆝ, U+119D)로 잘못 입력된 표기를 일반 '이'(ᅵ, U+1175) 모음으로 교정:
      '왕ᄋᆝᇡ다' -> '왕이ᇡ다'
    """
    if not text:
        return text
    # ᆝ(U+119D, 아래아+이) -> ᅵ(U+1175, 이 모음) 교정
    text = text.replace('\u110B\u119D\u11E1', '\u110B\u1175\u11E1')
    text = text.replace('왕ᄋᆝᇡ다', '왕이ᇡ다')
    return text


def convert_pua_to_unicode(text):
    """사전 텍스트 내 한양 PUA 문자를 표준 UTF-8 조합형 한글 자모로 치환 및 원문 오표기 교정."""
    if not text:
        return text
    converted = _PUA_PATTERN.sub(lambda m: PUA_TO_UNICODE[m.group(0)], text)
    return correct_dialect_typos(converted)


def parse_gyeongju_dictionary(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = convert_pua_to_unicode(f.read())

    # 1. 표제어 단위로 분리 (단어 뒤에 숫자가 있거나 괄호가 붙는 케이스 포함)
    # 예: 가1 [가아′], 가구2(家具-) [가아′구우′]
    # 수정: 대괄호([) 앞에 오는 모든 텍스트를 표제어 영역으로 인식
    raw_entries = re.split(r'\n(?=[^\s\[]+(?:\s*\d+)?(?:\(.*?\))?\s*\[)', content)
    
    dictionary_data = []

    # 품사 기호 유니코드 패턴 (체언, 용언, 부사 등 방언사전 고유 품사 부호)
    pos_pattern_str = r'[󰃃󰂿󰃰󰂽󰃌󰃲󰃥󰃆󰂴󰂳󰃓󰃫󰃩]+'
    # 1. 품사 기호가 있는 경우: 발음 내부의 중첩 대괄호 [...]를 모두 품어 품사 직전의 ']'까지 탐욕적 매칭
    p_with_pos = re.compile(rf'^([^\s\[]+)\s*\[(.*)\]\s*({pos_pattern_str})\s*(.*?)(?=\n\t¶|\n\t󰃾|\n|$)', re.DOTALL)
    # 2. 품사 기호가 없는 경우 (감탄사/호격 등)
    p_no_pos = re.compile(r'^([^\s\[]+)\s*\[(.*?)\]\s*(.*?)(?=\n\t¶|\n\t󰃾|\n|$)', re.DOTALL)

    for raw in raw_entries:
        if not raw.strip(): continue
        
        # 2. 기본 정보 추출 (단어, 발음, 품사기호, 정의)
        m = p_with_pos.match(raw)
        if m:
            word = m.group(1)
            pronunciation = m.group(2)
            pos_symbol = m.group(3)
            definition = m.group(4).strip().replace('\n', ' ')
        else:
            m2 = p_no_pos.match(raw)
            if not m2: continue
            word = m2.group(1)
            pronunciation = m2.group(2)
            pos_symbol = ""
            definition = m2.group(3).strip().replace('\n', ' ')
            
        # --- [수정 구간: 표제어 정규화] ---
        # 1. 한자 및 괄호 제거: (家具-) 형태 삭제
        # 2. 특수 기호 제거: - 등 삭제
        word_clean = re.sub(r'\(\{([^}]+)\}\)', r'{\1}', word)
        word_clean = re.sub(r'\(.*?\)', '', word_clean) # 괄호와 내용물 삭제
        word_clean = re.sub(r'[^\u1100-\u11FF\u3131-\u318E\uA960-\uA97F\uD7B0-\uD7FF\uE000-\uF8FF가-힣a-zA-Z0-9]', '', word_clean) # 현대·옛한글 자모 및 PUA 보존
        
        # 검색 전용 필드 (숫자까지 제거한 순수 한글명)
        word_pure = re.sub(r'\d+', '', word_clean)
        # -------------------------------

        item = {
            "word": word,                    # 원본: 가구2(家具-)
            "word_clean": word_clean,        # 정제: 가구2 (숫자 유지)
            "word_pure": word_pure,          # 검색용: 가구 (숫자 제거)
            "pronunciation": pronunciation,
            "pos_symbol": pos_symbol,
            "definition": definition,
            "examples": [],
            "idioms": []
        }

        # 3. 예문 추출 (생략 없이 유지)
        examples = re.findall(r'¶(.*?)\s*<(.*?)>', raw, re.DOTALL)
        for ex in examples:
            item["examples"].append({
                "dialect": ex[0].strip(),
                "standard": ex[1].strip()
            })

        # 4. 관용구/속담 추출 (생략 없이 유지)
        idioms = re.findall(r'󰃾(.*?)\s*<(.*?)>', raw)
        for idm in idioms:
            item["idioms"].append({
                "phrase": idm[0].strip(),
                "meaning": idm[1].strip()
            })

        dictionary_data.append(item)

    return dictionary_data
def save_secure_split_json(data, base_filename, xor_key="gyeongju_secret"):
    """
    JSON 데이터를 압축, 암호화 후 4개의 파일로 분할 저장
    """
    # 1. JSON 직렬화
    json_str = json.dumps(data, ensure_ascii=False)
    
    # 2. Gzip 압축 (용량 최적화)
    compressed = gzip.compress(json_str.encode('utf-8'))
    
    # 3. XOR 암호화 (단순 보안)
    key_bytes = xor_key.encode('utf-8')
    encrypted = bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(compressed)])
    
    # 4. Base64 인코딩 (텍스트 파일 저장용)
    b64_encoded = base64.b64encode(encrypted).decode('utf-8')
    
    # 5. 4분할 로직
    total_len = len(b64_encoded)
    chunk_size = math.ceil(total_len / 4)
    
    for i in range(4):
        start = i * chunk_size
        end = start + chunk_size
        chunk_data = b64_encoded[start:end]
        
        file_name = f"{base_filename}_{i+1}.bin"
        with open(file_name, 'w', encoding='utf-8') as f:
            f.write(chunk_data)
        print(f"저장 완료: {file_name} ({len(chunk_data)} bytes)")


# 파일명에 맞춰 실행
# result = parse_gyeongju_dictionary('경주지역어 대사전-251015-본문s.txt')
# with open('gyeongju_dict.json', 'w', encoding='utf-8') as f:
#     json.dump(result, f, ensure_ascii=False, indent=4)

# --- 실행부 (사용자 요청: 아직 최종 파일 등은 만들지 않고 대기) ---
# 1. 데이터 파싱
# if __name__ == '__main__':
#     result = parse_gyeongju_dictionary('경주지역어 대사전-260404-본문사_발24d6.txt')
#     with open('gyeongju_dict_all.json', 'w', encoding='utf-8') as f:
#         json.dump(result, f, ensure_ascii=False, indent=4)
#     # 2. 암호화 및 분할 저장 실행
#     save_secure_split_json(result, "gyeongju_data")
# 실행 및 저장 로직은 동일
