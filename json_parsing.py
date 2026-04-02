import re
import json

def parse_gyeongju_dictionary(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. 표제어 단위로 분리 (단어 뒤에 숫자가 있거나 괄호가 붙는 케이스 포함)
    # 예: 가1 [가아′], 가구2(家具-) [가아′구우′]
    # 수정: 대괄호([) 앞에 오는 모든 텍스트를 표제어 영역으로 인식
    raw_entries = re.split(r'\n(?=[^\s\[]+(?:\s*\d+)?(?:\(.*?\))?\s*\[)', content)
    
    dictionary_data = []

    for raw in raw_entries:
        if not raw.strip(): continue
        
        # 2. 기본 정보 추출 (단어, 발음, 품사기호, 정의)
        header_match = re.match(r'^([^\s\[]+)\s*\[(.*?)\]\s*([^\s]+)\s*(.*?)(?=\n\t¶|\n\t󰃾|\n|$)', raw, re.DOTALL)
        
        if header_match:
            word = header_match.group(1)
            
            # --- [수정 구간: 표제어 정규화] ---
            # 1. 한자 및 괄호 제거: (家具-) 형태 삭제
            # 2. 특수 기호 제거: - 등 삭제
            word_clean = re.sub(r'\(.*?\)', '', word) # 괄호와 내용물 삭제
            word_clean = re.sub(r'[^ㄱ-ㅎ가-힣a-zA-Z0-9]', '', word_clean) # 한글/영문/숫자 외 제거
            
            # 검색 전용 필드 (숫자까지 제거한 순수 한글명)
            word_pure = re.sub(r'\d+', '', word_clean)
            # -------------------------------

            item = {
                "word": word,                    # 원본: 가구2(家具-)
                "word_clean": word_clean,        # 정제: 가구2 (숫자 유지)
                "word_pure": word_pure,          # 검색용: 가구 (숫자 제거)
                "pronunciation": header_match.group(2),
                "pos_symbol": header_match.group(3),
                "definition": header_match.group(4).strip().replace('\n', ' '),
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

# 실행 및 저장 로직은 동일
# result = parse_gyeongju_dictionary('경주지역어 대사전-251015-본문s.txt')

# 파일명에 맞춰 실행
result = parse_gyeongju_dictionary('경주지역어 대사전-251015-본문s.txt')
with open('gyeongju_dict.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=4)