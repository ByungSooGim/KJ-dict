import re
import json
import gzip
import base64
import math
def parse_gyeongju_dictionary(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

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
        word_clean = re.sub(r'\(.*?\)', '', word) # 괄호와 내용물 삭제
        word_clean = re.sub(r'[^\u1100-\u11FF\u3131-\u318E\uA960-\uA97F\uD7B0-\uD7FF가-힣a-zA-Z0-9]', '', word_clean) # 현대·옛한글 자모 보존
        
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

        # 4. 관용구/속담 추출 (full text 및 구성 요소 보존)
        idiom_matches = re.findall(r'󰃾(.*)', raw)
        for idm_str in idiom_matches:
            full_text = idm_str.strip()
            if not full_text:
                continue

            # 구조 분리 (phrase <standard> meaning)
            m_idm = re.match(r'^(.*?)\s*<([^>]*)>(.*)$', full_text)
            if m_idm:
                phrase_part = m_idm.group(1).strip()
                standard_part = m_idm.group(2).strip()
                meaning_part = m_idm.group(3).strip()
            else:
                phrase_part = full_text
                standard_part = ""
                meaning_part = ""

            item["idioms"].append({
                "full": full_text,
                "phrase": phrase_part,
                "standard": standard_part,
                "meaning": meaning_part
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

# --- 실행부 ---
# 1. 데이터 파싱

result = parse_gyeongju_dictionary('경주지역어 대사전-260404-본문사_발25D14.txt')
with open('gyeongju_dict_all.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=4)

#result = parse_gyeongju_dictionary('경주지역어 대사전-251015-본문s.txt')

# 2. 암호화 및 분할 저장 실행
save_secure_split_json(result, "gyeongju_data")
# 실행 및 저장 로직은 동일
