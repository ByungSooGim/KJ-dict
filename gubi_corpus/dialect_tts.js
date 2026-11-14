function getEffectiveSpeechRate(fallback = 0.76) {
    const saved = localStorage.getItem('web_tts_user_speed');
    if (saved) {
        const val = parseFloat(saved);
        if (!isNaN(val) && val >= 0.5 && val <= 1.5) return val;
    }
    return fallback;
}

function onSpeedSliderChange(val) {
    const num = parseFloat(val);
    if (isNaN(num)) return;
    const badge = document.getElementById('speedValBadge');
    if (badge) badge.innerText = `${num.toFixed(2)}x`;
    localStorage.setItem('web_tts_user_speed', num.toFixed(2));

    // 학습 프로필 저장소(gyeongju_learned_prosody_v3)의 baseRate도 동기화
    try {
        const profile = getLearnedProsodyProfile();
        profile.baseRate = Number(num.toFixed(2));
        localStorage.setItem('gyeongju_learned_prosody_v3', JSON.stringify(profile));
    } catch (e) {}
}

function initSpeedSlider() {
    const currentSpeed = getEffectiveSpeechRate(0.76);
    const slider = document.getElementById('speechRateSlider');
    const badge = document.getElementById('speedValBadge');
    if (slider) slider.value = String(currentSpeed);
    if (badge) badge.innerText = `${currentSpeed.toFixed(2)}x`;

    const hp = getEffectiveHighPitchRatio();
    const hpSlider = document.getElementById('highPitchSlider');
    const hpBadge = document.getElementById('highPitchBadge');
    if (hpSlider) hpSlider.value = String(hp);
    if (hpBadge) hpBadge.innerText = `${hp.toFixed(2)}x`;
}

// ========================================================
// [강세(′) 고조 배율 조절 헬퍼] - 2번(하늘색) 스피커 전용 (demo_prosody.html의 highPitchRatio 1.48x 연동)
// ========================================================
const DEFAULT_HIGH_PITCH_RATIO = 1.48;

function getEffectiveHighPitchRatio() {
    try {
        const saved = localStorage.getItem('gyeongju_learned_prosody_v3');
        if (saved) {
            const parsed = JSON.parse(saved);
            if (parsed && typeof parsed.highPitchRatio === 'number' && parsed.highPitchRatio >= 1.0 && parsed.highPitchRatio <= 2.5) {
                return parsed.highPitchRatio;
            }
        }
    } catch (e) {}
    return DEFAULT_HIGH_PITCH_RATIO;
}

function onHighPitchSliderChange(val) {
    const num = parseFloat(val);
    if (isNaN(num)) return;
    const badge = document.getElementById('highPitchBadge');
    if (badge) badge.innerText = `${num.toFixed(2)}x`;
    try {
        const profile = getLearnedProsodyProfile();
        profile.highPitchRatio = Number(num.toFixed(2));
        localStorage.setItem('gyeongju_learned_prosody_v3', JSON.stringify(profile));
    } catch (e) {}
}

// Chrome은 첫 호출 시 getVoices()가 빈 배열을 반환하므로 미리 음성 목록을 로드해 둠
// (첫 클릭에서 남성 판별이 실패해 엉뚱한 피치로 읽히는 버그 방지)
if (window.speechSynthesis) {
    try {
        window.speechSynthesis.getVoices();
        window.speechSynthesis.addEventListener('voiceschanged', () => window.speechSynthesis.getVoices());
    } catch (e) {}
}

// ========================================================
// [2번 TTS 핵심 엔진]: demo_prosody.html의 "🌊 2. 물 흐르듯 연속 사투리 합성 (무단절 WSOLA)" 100% 동일 이식
// - 1단계: 로컬 Praat edge_server.py 실행 시 Cross-Correlation Phase-Locked Resampling WSOLA 합성 파형 재생
// - 2단계: 브라우저 단독 실행 시 통일 남성 저음역 + 장모음 3모라 연결 연장 + 내 학습 억양(localStorage) 연속 발화
// ========================================================

function getLearnedProsodyProfile() {
    const currentSpeed = getEffectiveSpeechRate(0.76);
    const def = {
        sampleCount: 45,
        baseF0Hz: 171,
        peakF0Hz: 243,
        highPitchRatio: 1.48,
        lowPitchRatio: 1.05,
        longStretch: 1.70,
        glideSlope: 0.93,
        endBoostSemitones: 1.0,
        baseRate: currentSpeed
    };
    try {
        const saved = localStorage.getItem('gyeongju_learned_prosody_v3');
        if (saved) {
            const parsed = JSON.parse(saved);
            if (parsed) return { ...def, ...parsed, baseRate: currentSpeed };
        }
    } catch (e) {}
    return def;
}

function getSkyProsodyParams() {
    const prof = getLearnedProsodyProfile();
    return {
        highPitch: Number(prof.highPitchRatio) || 1.48,
        lowPitch: Number(prof.lowPitchRatio) || 1.05,
        longStretch: Number(prof.longStretch) || 1.70,
        glide: Number(prof.glideSlope) || 0.93,
        endBoostSemitones: Number(prof.endBoostSemitones) || 1.0,
        baseRate: Number(prof.baseRate) || 0.76
    };
}

function isExplicitMaleVoice(v) {
    if (!v) return false;
    const str = ((v.name || "") + " " + (v.voiceURI || "")).toLowerCase();
    return /injoon|인준|hyunsu|현수|bongjin|봉진|gookmin|국민|male|남성|남자|ism|kob|wavenet-c|wavenet-d|neural2-c|standard-c|standard-d/i.test(str);
}

// 1. 한국어 남성 음성 탐색 헬퍼 (로컬 피치 변조가 잘 먹는 음성 우선 선택)
function getKoreanMaleVoice() {
    if (!window.speechSynthesis) return null;
    const voices = window.speechSynthesis.getVoices();
    if (!voices || voices.length === 0) return null;

    const koVoices = voices.filter(v => v.lang && (v.lang.startsWith('ko') || v.lang === 'ko-KR'));
    if (koVoices.length === 0) return null;

    // 0. 사용자가 수동 선택해둔 보이스 URI가 있으면 우선 적용
    const savedUri = localStorage.getItem('web_tts_male_voice_uri');
    if (savedUri) {
        const found = koVoices.find(v => (v.voiceURI === savedUri || v.name === savedUri));
        if (found) return found;
    }

    // 1. 이름이나 URI에 명시적 남성 식별자(InJoon, 인준, Hyunsu, Male 등)가 있는 음성 우선 탐색
    const explicitMale = koVoices.find(v => isExplicitMaleVoice(v));
    if (explicitMale) return explicitMale;

    // 2. 명시적 남성 보이스가 없을 때(Windows Chrome 기본 등):
    // 원격 여성 보이스(Google 한국의, localService: false) 대신 깊은 남성 피치 하향(0.35~0.72)이 즉시 적용되는 로컬 보이스(localService: true) 우선 선택!
    const localKo = koVoices.find(v => v.localService);
    if (localKo) return localKo;

    return koVoices[0];
}

// 2번 남성 음성 수동 선택 (2번 스피커 우클릭 시)
function setMaleVoiceChoice() {
    if (!window.speechSynthesis) return;
    const voices = window.speechSynthesis.getVoices().filter(v => v.lang && (v.lang.startsWith('ko') || v.lang === 'ko-KR'));
    if (voices.length === 0) {
        alert("브라우저에서 사용 가능한 한국어 음성을 찾을 수 없습니다.");
        return;
    }
    const current = getKoreanMaleVoice();
    const voiceListStr = voices.map((v, i) => `${i + 1}. ${v.name} ${v === current ? "★[현재 선택]" : ""}`).join('\n');
    const choice = prompt(`2번 TTS에서 사용할 한국어 음성 번호를 선택하세요:\n\n${voiceListStr}\n\n(비워두면 자동 남성 음성 탐색)`);
    if (choice !== null) {
        if (choice.trim() === "") {
            localStorage.removeItem('web_tts_male_voice_uri');
            alert("기본 자동 남성 음성 탐색으로 재설정되었습니다.");
        } else {
            const idx = parseInt(choice.trim()) - 1;
            if (!isNaN(idx) && voices[idx]) {
                localStorage.setItem('web_tts_male_voice_uri', voices[idx].voiceURI || voices[idx].name);
                alert(`선택된 음성: ${voices[idx].name}`);
            }
        }
    }
}

// 한글 자모 분해 및 장모음(사아·가아·초온·서엉·해애) 3모라 연결 연장 파서 (demo_prosody.html 동일)
const DIALECT_TONE_CHARS = new Set(["'", "′", "″", "ː", "ˈ", "ˌ", "^"]);

function decomposeHangulSyl(ch) {
    const code = ch.charCodeAt(0);
    if (code < 0xAC00 || code > 0xD7A3) return null;
    const offset = code - 0xAC00;
    return {
        cho: Math.floor(offset / (21 * 28)),
        jung: Math.floor((offset % (21 * 28)) / 28),
        jong: offset % 28
    };
}

function composeHangulSyl(cho, jung, jong) {
    return String.fromCharCode(0xAC00 + (cho * 21 + jung) * 28 + jong);
}

const DIALECT_LONG_VOWEL_TAIL_MAP = {
    0: [0], 1: [1, 5], 2: [0, 2], 3: [1, 3, 5], 4: [4], 5: [5, 1],
    6: [4, 6], 7: [5, 1, 7], 8: [8], 9: [0, 9], 10: [1, 5, 10],
    11: [5, 1, 11], 12: [8, 12], 13: [13], 14: [4, 14], 15: [5, 1, 15],
    16: [20, 16], 17: [13, 17], 18: [18], 19: [20, 19], 20: [20]
};

// 복모음(이중모음: ㅑ, ㅒ, ㅕ, ㅖ, ㅘ, ㅙ, ㅚ, ㅛ, ㅝ, ㅞ, ㅟ, ㅠ, ㅢ) 연장 시
// 반모음(j/w)이 재발음되어 "야야", "여여", "요요", "웨웨"처럼 들리는 현상을 막기 위해
// 복모음의 끝 단모음(ㅏ, ㅐ, ㅓ, ㅔ, ㅗ, ㅜ, ㅣ)으로 치환하는 매핑 테이블
const PURE_SUSTAIN_VOWEL_INDEX = {
    0: 0,   // ㅏ -> ㅏ (아)
    1: 1,   // ㅐ -> ㅐ (애)
    2: 0,   // ㅑ -> ㅏ (야 -> 아)
    3: 1,   // ㅒ -> ㅐ (얘 -> 애)
    4: 4,   // ㅓ -> ㅓ (어)
    5: 5,   // ㅔ -> ㅔ (에)
    6: 4,   // ㅕ -> ㅓ (여 -> 어)
    7: 5,   // ㅖ -> ㅔ (예 -> 에)
    8: 8,   // ㅗ -> ㅗ (오)
    9: 0,   // ㅘ -> ㅏ (와 -> 아)
    10: 1,  // ㅙ -> ㅐ (왜 -> 애)
    11: 5,  // ㅚ -> ㅔ (외 -> 에)
    12: 8,  // ㅛ -> ㅗ (요 -> 오)
    13: 13, // ㅜ -> ㅜ (우)
    14: 4,  // ㅝ -> ㅓ (워 -> 어)
    15: 5,  // ㅞ -> ㅔ (웨 -> 에)
    16: 20, // ㅟ -> ㅣ (위 -> 이)
    17: 13, // ㅠ -> ㅜ (유 -> 우)
    18: 18, // ㅡ -> ㅡ (으)
    19: 20, // ㅢ -> ㅣ (의 -> 이)
    20: 20  // ㅣ -> ㅣ (이)
};

function getPureVowelSustainChar(jungIdx) {
    const pureJung = PURE_SUSTAIN_VOWEL_INDEX[jungIdx] !== undefined ? PURE_SUSTAIN_VOWEL_INDEX[jungIdx] : jungIdx;
    return composeHangulSyl(11, pureJung, 0);
}

function collapseDialectLongPair(ch1, ch2) {
    const d1 = decomposeHangulSyl(ch1);
    const d2 = decomposeHangulSyl(ch2);
    if (!d1 || !d2) return null;
    const allowed = DIALECT_LONG_VOWEL_TAIL_MAP[d1.jung];
    if (d1.jong === 0 && d2.cho === 11 && allowed && allowed.includes(d2.jung)) {
        return composeHangulSyl(d1.cho, d1.jung, d2.jong);
    }
    return null;
}

function parseDialectWordForSpeech(rawWord) {
    const chars = Array.from(rawWord.trim());
    const n = chars.length;
    const rawSyls = [];
    let i = 0;
    while (i < n) {
        const ch = chars[i];
        if (ch >= '가' && ch <= '힣') {
            let j = i + 1;
            let hasTone = false;
            while (j < n && DIALECT_TONE_CHARS.has(chars[j])) {
                hasTone = true;
                j++;
            }
            let punc = "";
            while (j < n && !(chars[j] >= '가' && chars[j] <= '힣') && !DIALECT_TONE_CHARS.has(chars[j])) {
                punc += chars[j];
                j++;
            }
            rawSyls.push({ char: ch, tone: hasTone ? 'H' : 'L', punc });
            i = j;
        } else {
            i++;
        }
    }

    const merged = [];
    let skip = false;
    for (let k = 0; k < rawSyls.length; k++) {
        if (skip) { skip = false; continue; }
        const cur = rawSyls[k];
        if (k + 1 < rawSyls.length && !cur.punc) {
            const nxt = rawSyls[k + 1];
            const collapsed = collapseDialectLongPair(cur.char, nxt.char);
            if (collapsed) {
                const isH = (cur.tone === 'H' || nxt.tone === 'H');
                const d2 = decomposeHangulSyl(nxt.char);
                const vowelTailChar = d2 ? getPureVowelSustainChar(d2.jung) : nxt.char;
                merged.push({
                    char: cur.char + nxt.char,
                    collapsedChar: collapsed,
                    rawPair: cur.char + nxt.char,
                    vowelTailChar,
                    tone: isH ? 'H' : 'L',
                    isLong: true,
                    punc: nxt.punc
                });
                skip = true;
                continue;
            }
        }
        merged.push({
            char: cur.char,
            collapsedChar: cur.char,
            rawPair: cur.char,
            vowelTailChar: cur.char,
            tone: cur.tone,
            isLong: false,
            punc: cur.punc
        });
    }
    return merged;
}

function parseDialectSentenceForSpeech(sentence) {
    const cleanSent = sentence.replace(/^\[|\]$/g, '').trim();
    const rawWords = cleanSent.split(/\s+/).filter(Boolean);
    return rawWords.map((rw, wIdx) => ({
        wordIndex: wIdx,
        raw: rw,
        syls: parseDialectWordForSpeech(rw)
    })).filter(w => w.syls.length > 0);
}

function formatSyllableForSpeech(s, mode, params, collapseLong = true) {
    if (mode !== 'prosody') {
        return s.collapsedChar + s.punc;
    }
    if (!s.isLong) {
        return s.char + s.punc;
    }
    if (!collapseLong) {
        return s.rawPair + s.punc;
    }
    const stretch = params ? params.longStretch : 1.68;
    const c1 = s.rawPair[0];
    const c2 = s.rawPair[1] || '';
    const vTail = s.vowelTailChar || c2;
    if (stretch >= 1.85) {
        return c1 + vTail + vTail + c2 + s.punc;
    } else if (stretch >= 1.32) {
        return c1 + vTail + c2 + s.punc;
    } else {
        return s.rawPair + s.punc;
    }
}

// ========================================================
// [3번(초록색) 스피커 전용: 어절 내 단음 강세(′) 1.12배 길이 연장 헬퍼]
// ========================================================
const DEFAULT_GREEN_SHORT_ACCENT_STRETCH = 1.12;

function getGreenShortAccentStretch() {
    const saved = parseFloat(localStorage.getItem('web_tts_green_short_stretch'));
    if (!isNaN(saved) && saved >= 1.0 && saved <= 1.5) return saved;
    return DEFAULT_GREEN_SHORT_ACCENT_STRETCH;
}

function setGreenShortAccentStretch() {
    const cur = getGreenShortAccentStretch();
    const input = prompt(
        "3번(초록색) TTS [단음 강세(′) 길이 연장 배율]을 설정하세요 (권장: 1.08 ~ 1.25):\n\n" +
        "• 기본값: 1.12 (단음 강세 음절을 1.12배 늘려 고음 도달 시간 확보 및 피치 상승 유도)\n" +
        "• 1.00에 가까울수록 2번(하늘색)과 비슷해지고, 1.15~1.25로 올릴수록 어절 내 강세 음절이 더 길고 높게 강조됩니다.\n\n" +
        "(비워두고 확인을 누르면 기본값 1.12로 초기화됩니다)",
        String(cur)
    );
    if (input !== null) {
        if (input.trim() === "") {
            localStorage.setItem('web_tts_green_short_stretch', String(DEFAULT_GREEN_SHORT_ACCENT_STRETCH));
            alert(`단음 강세 연장 배율이 기본값(${DEFAULT_GREEN_SHORT_ACCENT_STRETCH}배)으로 재설정되었습니다.`);
        } else {
            const val = parseFloat(input.trim());
            if (!isNaN(val) && val >= 1.0 && val <= 1.5) {
                localStorage.setItem('web_tts_green_short_stretch', val.toFixed(2));
                alert(`단음 강세 연장 배율이 ${val.toFixed(2)}배로 저장되었습니다.`);
            }
        }
    }
}

// 3번(초록색) 전용 음절 포맷터:
// - 장모음(isLong)은 2번과 동일하게 3모라로 연장하되 복모음 꼬리는 단모음으로 매끄럽게 처리
// - 단모음 강세(!s.isLong && s.tone === 'H')는 연장 배율(기본 1.12배 >= 1.08)일 때
//   받침 없는 개음절의 모음 핵을 미세 공명시키되,
//   복모음(ㅑ, ㅕ, ㅛ, ㅠ, ㅞ, ㅘ, ㅝ 등)은 반드시 끝 단모음(ㅏ, ㅓ, ㅗ, ㅜ, ㅔ 등)을 붙여
//   "야야", "여여"가 아닌 "야아", "여어", "요오", "유우", "웨에"로 자연스럽게 이어지도록 처리!
function formatSyllableForGreenSpeech(s, params, collapseLong = true, shortAccentStretch = 1.12) {
    if (s.isLong) {
        const c1 = s.rawPair[0];
        const c2 = s.rawPair[1] || '';
        const d1 = decomposeHangulSyl(c1);
        const d2 = decomposeHangulSyl(c2);
        const vTail = s.vowelTailChar || (d1 ? getPureVowelSustainChar(d1.jung) : c2);
        // c2 자체도 복모음(예: 야+야)으로 적혀 있다면 단모음(아+받침)으로 교정하여 "야야" 발음 방지
        const safeC2 = (d2 && d2.cho === 11 && PURE_SUSTAIN_VOWEL_INDEX[d2.jung] !== undefined)
            ? composeHangulSyl(11, PURE_SUSTAIN_VOWEL_INDEX[d2.jung], d2.jong)
            : c2;
        const stretch = params ? params.longStretch : 1.68;
        if (stretch >= 1.85) {
            return c1 + vTail + vTail + safeC2 + s.punc;
        } else if (stretch >= 1.32) {
            return c1 + vTail + safeC2 + s.punc;
        }
        return c1 + safeC2 + s.punc;
    }
    if (s.tone === 'H' && shortAccentStretch >= 1.08 && !s.punc) {
        const dec = decomposeHangulSyl(s.char);
        if (dec && dec.jong === 0) {
            const vTail = getPureVowelSustainChar(dec.jung);
            return s.char + vTail;
        }
    }
    return s.char + (s.punc || "");
}

// ========================================================
// [무단절 WSOLA 음향 신호 처리 엔진] (demo_prosody.html 100% 동일 + 3번 단음 강세 연장 지원)
// ========================================================
let skyAudioCtx = null;
let skyCurrentSourceNode = null;
const skyBaseAudioCache = new Map();
let skySpeakToken = 0;

function getSkyAudioContext() {
    if (!skyAudioCtx) {
        const AC = window.AudioContext || window.webkitAudioContext;
        skyAudioCtx = new AC();
    }
    if (skyAudioCtx.state === 'suspended') {
        skyAudioCtx.resume();
    }
    return skyAudioCtx;
}

function stopSkyProsodyAudio() {
    skySpeakToken++;
    if (skyCurrentSourceNode) {
        try { skyCurrentSourceNode.stop(); } catch (e) {}
        skyCurrentSourceNode = null;
    }
    if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
    }
}

async function fetchContinuousSentenceBuffer(cleanText) {
    if (skyBaseAudioCache.has(cleanText)) {
        return skyBaseAudioCache.get(cleanText);
    }
    const ctx = getSkyAudioContext();
    try {
        const ctrl = new AbortController();
        const tid = setTimeout(() => ctrl.abort(), 200);
        const res = await fetch("http://localhost:5050/prosody", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: cleanText, mode: "orig" }),
            signal: ctrl.signal
        });
        clearTimeout(tid);
        if (res.ok) {
            const arr = await res.arrayBuffer();
            const buf = await ctx.decodeAudioData(arr);
            skyBaseAudioCache.set(cleanText, buf);
            return buf;
        }
    } catch (e) {}
    return null;
}

function analyzeSpeechEnvelope(samples, sr) {
    const hop = Math.floor(sr * 0.01);
    const win = Math.floor(sr * 0.025);
    const numFrames = Math.max(1, Math.floor((samples.length - win) / hop));
    const rms = new Float32Array(numFrames);
    let maxRms = 1e-6;

    for (let f = 0; f < numFrames; f++) {
        const start = f * hop;
        let sum = 0;
        for (let i = 0; i < win; i++) {
            const v = samples[start + i] || 0;
            sum += v * v;
        }
        rms[f] = Math.sqrt(sum / win);
        if (rms[f] > maxRms) maxRms = rms[f];
    }

    const thresh = maxRms * 0.06;
    let firstFrame = 0;
    let lastFrame = numFrames - 1;
    while (firstFrame < numFrames && rms[firstFrame] < thresh) firstFrame++;
    while (lastFrame > firstFrame && rms[lastFrame] < thresh) lastFrame--;

    const startSec = Math.max(0.01, (firstFrame * hop) / sr - 0.02);
    const endSec = Math.min(samples.length / sr - 0.01, (lastFrame * hop) / sr + 0.03);
    return { startSec, endSec, rms, maxRms, hopSec: 0.01 };
}

function buildContinuousProsodyCurves(words, startSec, endSec, totalDurSec, params, rms, maxRms, isGreenBoost = false) {
    const dt = 0.01;
    const numSteps = Math.ceil(totalDurSec / dt) + 2;
    const pitchCurve = new Float32Array(numSteps).fill(1.0);
    const durCurve = new Float32Array(numSteps).fill(1.0 / params.baseRate);
    const wordIdxCurve = new Int16Array(numSteps).fill(-1);

    const speechSpan = Math.max(0.15, endSec - startSec);
    const collapseLong = true;
    const shortAccentStretch = isGreenBoost ? getGreenShortAccentStretch() : 1.08;
    const items = [];
    words.forEach((w, wIdx) => {
        w.syls.forEach((s, sIdx) => {
            const isWordEnd = (sIdx === w.syls.length - 1);
            const hasComma = /[,\.!\?]/.test(s.punc || "");
            const origWeight = s.isLong ? (collapseLong ? 1.12 : 1.75) : 1.0;
            items.push({
                syl: s,
                wordIdx: wIdx,
                isWordEnd,
                origWeight
            });
            if (hasComma) {
                items.push({ isPause: true, origWeight: 0.55, wordIdx: wIdx });
            }
        });
        items.push({ isPause: true, origWeight: 0.22, wordIdx: wIdx });
    });

    const totalOrigW = items.reduce((a, b) => a + b.origWeight, 0) || 1.0;
    let curT = startSec;
    const sylSpans = [];

    items.forEach(it => {
        const spanDur = (it.origWeight / totalOrigW) * speechSpan;
        const t0 = curT;
        const t1 = curT + spanDur;
        curT = t1;
        if (!it.isPause) {
            sylSpans.push({
                t0,
                t1,
                tMid: 0.5 * (t0 + t1),
                syl: it.syl,
                wordIdx: it.wordIdx,
                isWordEnd: it.isWordEnd
            });
        }
    });

    const getDeclinationComp = (t) => {
        const prog = Math.max(0, Math.min(1, (t - startSec) / speechSpan));
        return 1.0 + prog * 0.08;
    };

    const keyPoints = [];
    const pHigh = params.lowPitch * params.highPitch;
    const pLow = pHigh; // 평음·고음 구분 없이 기존 고음 기본 피치로 통합
    const endBoostRatio = Math.pow(2, params.endBoostSemitones / 12.0);

    if (sylSpans.length > 0) {
        keyPoints.push({ t: 0, p: pLow });
        keyPoints.push({ t: startSec, p: sylSpans[0].syl.tone === 'H' ? pLow + (pHigh - pLow) * 0.35 : pLow });

        sylSpans.forEach((sp) => {
            const s = sp.syl;
            const dur = sp.t1 - sp.t0;
            const comp = getDeclinationComp(sp.tMid);
            const targetH = pHigh * comp;
            const targetL = pLow * comp;

            const i0 = Math.max(0, Math.floor(sp.t0 / dt));
            const i1 = Math.min(numSteps - 1, Math.ceil(sp.t1 / dt));
            for (let k = i0; k <= i1; k++) {
                wordIdxCurve[k] = sp.wordIdx;
                if (s.isLong) {
                    const localPos = (k * dt - sp.t0) / Math.max(0.01, dur);
                    const bell = Math.sin(Math.PI * Math.max(0, Math.min(1, localPos)));
                    const effectiveStretch = collapseLong ? params.longStretch : (1.0 + (params.longStretch - 1.0) * 0.55);
                    const stretchHere = 1.0 + (effectiveStretch - 1.0) * Math.pow(bell, 0.75);
                    durCurve[k] = stretchHere / params.baseRate;
                } else if (s.tone === 'H') {
                    if (isGreenBoost) {
                        // 3번(초록색): 단음 강세 음절의 모음 중심부를 종 모양(Hanning bell)으로 감싸
                        // 설정된 배율(기본 1.18배)만큼 매끄럽게 늘려 고음 도달 시간 확보!
                        const localPos = (k * dt - sp.t0) / Math.max(0.01, dur);
                        const bell = Math.sin(Math.PI * Math.max(0, Math.min(1, localPos)));
                        const stretchHere = 1.0 + (shortAccentStretch - 1.0) * Math.pow(bell, 0.65);
                        durCurve[k] = stretchHere / params.baseRate;
                    } else {
                        durCurve[k] = 1.08 / params.baseRate;
                    }
                } else {
                    durCurve[k] = 0.96 / params.baseRate;
                }
            }

            // 3번(초록색)에서는 단음 강세가 1.1~1.2배 늘어난 만큼 피치 정점(Plateau)을 더 넓고 높게 유지
            const shortPeakBoost = (isGreenBoost && !s.isLong && s.tone === 'H')
                ? (1.0 + Math.max(0, shortAccentStretch - 1.0) * 0.35)
                : 1.0;

            if (sp.isWordEnd && s.tone === 'H') {
                const startGlide = pLow * comp + (targetH - pLow * comp) * (1.0 - params.glide * 0.65);
                keyPoints.push({ t: sp.t0 + dur * (isGreenBoost ? 0.16 : 0.20), p: startGlide });
                keyPoints.push({ t: sp.t0 + dur * 0.85, p: targetH * endBoostRatio * shortPeakBoost });
                keyPoints.push({ t: sp.t1, p: targetH * endBoostRatio * shortPeakBoost });
            } else if (s.isLong && s.tone === 'H') {
                const entryP = targetL + (targetH - targetL) * (1.0 - params.glide * 0.75);
                keyPoints.push({ t: sp.t0 + dur * 0.18, p: entryP });
                keyPoints.push({ t: sp.t0 + dur * 0.82, p: targetH });
            } else if (s.tone === 'H') {
                const entryP = targetL + (targetH - targetL) * (1.0 - params.glide * 0.5);
                if (isGreenBoost) {
                    // 어절 내 단음 강세: 빠르게 고음으로 치고 올라가 82% 지점까지 고음 평탄부(High Plateau) 유지
                    keyPoints.push({ t: sp.t0 + dur * 0.15, p: entryP });
                    keyPoints.push({ t: sp.t0 + dur * 0.45, p: targetH * shortPeakBoost });
                    keyPoints.push({ t: sp.t0 + dur * 0.82, p: targetH * shortPeakBoost });
                } else {
                    keyPoints.push({ t: sp.t0 + dur * 0.22, p: entryP });
                    keyPoints.push({ t: sp.t0 + dur * 0.75, p: targetH });
                }
            } else {
                keyPoints.push({ t: sp.tMid, p: targetL });
            }
        });

        keyPoints.push({ t: totalDurSec, p: keyPoints[keyPoints.length - 1].p });
    }

    keyPoints.sort((a, b) => a.t - b.t);
    for (let k = 0; k < keyPoints.length - 1; k++) {
        const pt1 = keyPoints[k];
        const pt2 = keyPoints[k + 1];
        if (pt2.t <= pt1.t) continue;
        const iStart = Math.max(0, Math.floor(pt1.t / dt));
        const iEnd = Math.min(numSteps - 1, Math.ceil(pt2.t / dt));
        for (let idx = iStart; idx <= iEnd; idx++) {
            const t = idx * dt;
            const frac = Math.max(0, Math.min(1, (t - pt1.t) / (pt2.t - pt1.t)));
            const smooth = 0.5 * (1.0 - Math.cos(Math.PI * frac));
            pitchCurve[idx] = pt1.p + (pt2.p - pt1.p) * smooth;
        }
    }

    if (rms && maxRms > 0) {
        for (let idx = 0; idx < numSteps; idx++) {
            const rVal = idx < rms.length ? rms[idx] : 0;
            if (rVal < maxRms * 0.12) {
                durCurve[idx] = 1.0 / params.baseRate;
            }
        }
    }

    return { pitchCurve, durCurve, wordIdxCurve, dt, sylSpans };
}

function synthesizeContinuousWSOLA(inBuffer, pitchCurve, durCurve, wordIdxCurve, dt) {
    const sr = inBuffer.sampleRate;
    const inSamples = inBuffer.getChannelData(0);
    const inLen = inSamples.length;

    const winSize = Math.floor(sr * 0.032) & ~1;
    const hopSyn = winSize >> 1;
    const searchRange = Math.floor(sr * 0.007);

    const hann = new Float32Array(winSize);
    for (let i = 0; i < winSize; i++) {
        hann[i] = 0.5 * (1.0 - Math.cos((2.0 * Math.PI * i) / winSize));
    }

    let estOutSamples = 0;
    for (let i = 0; i < durCurve.length; i++) {
        estOutSamples += Math.ceil(dt * sr * durCurve[i]);
    }
    const maxOutLen = estOutSamples + winSize * 4;
    const outSamples = new Float32Array(maxOutLen);
    const outWordTimeline = [];

    let inPos = 0.0;
    let outPos = 0;

    const sampleCubic = (pos) => {
        const idx = Math.floor(pos);
        if (idx < 1 || idx >= inLen - 2) {
            return (idx >= 0 && idx < inLen) ? inSamples[idx] : 0.0;
        }
        const frac = pos - idx;
        const y0 = inSamples[idx - 1];
        const y1 = inSamples[idx];
        const y2 = inSamples[idx + 1];
        const y3 = inSamples[idx + 2];
        const c0 = y1;
        const c1 = 0.5 * (y2 - y0);
        const c2 = y0 - 2.5 * y1 + 2.0 * y2 - 0.5 * y3;
        const c3 = 0.5 * (y3 - y0) + 1.5 * (y1 - y2);
        return ((c3 * frac + c2) * frac + c1) * frac + c0;
    };

    while (inPos < inLen - winSize * 2 && outPos + winSize < maxOutLen) {
        const curSec = inPos / sr;
        const curveIdx = Math.min(pitchCurve.length - 1, Math.max(0, Math.floor(curSec / dt)));
        const pRatio = pitchCurve[curveIdx];
        const dRatio = durCurve[curveIdx];
        const wIdx = wordIdxCurve[curveIdx];

        outWordTimeline.push({ outSec: outPos / sr, wordIdx: wIdx });

        let bestDelta = 0;
        if (outPos > 0) {
            let maxCorr = -1e18;
            const checkLen = Math.min(hopSyn >> 1, Math.floor(sr * 0.008));
            for (let delta = -searchRange; delta <= searchRange; delta += 2) {
                const candStart = inPos + delta;
                if (candStart < 1 || candStart + winSize * pRatio >= inLen - 2) continue;
                let corr = 0.0;
                for (let j = 0; j < checkLen; j += 2) {
                    const existing = outSamples[outPos + j];
                    const candVal = inSamples[Math.floor(candStart + j * pRatio)];
                    corr += existing * candVal;
                }
                if (corr > maxCorr) {
                    maxCorr = corr;
                    bestDelta = delta;
                }
            }
        }

        const readStart = Math.max(1, inPos + bestDelta);
        for (let i = 0; i < winSize; i++) {
            const val = sampleCubic(readStart + i * pRatio);
            outSamples[outPos + i] += val * hann[i];
        }

        outPos += hopSyn;
        inPos += hopSyn / Math.max(0.35, dRatio);
    }

    const finalLen = Math.max(winSize, outPos + hopSyn);
    const ctx = getSkyAudioContext();
    const outBuffer = ctx.createBuffer(1, finalLen, sr);
    outBuffer.getChannelData(0).set(outSamples.subarray(0, finalLen));

    return { outBuffer, outWordTimeline };
}

function synthesizeContinuousProsodyBuffer(baseBuffer, words, params, isGreenBoost = false) {
    const sr = baseBuffer.sampleRate;
    const samples = baseBuffer.getChannelData(0);
    const totalDurSec = baseBuffer.duration;
    const { startSec, endSec, rms, maxRms } = analyzeSpeechEnvelope(samples, sr);
    const { pitchCurve, durCurve, wordIdxCurve, dt } = buildContinuousProsodyCurves(
        words, startSec, endSec, totalDurSec, params, rms, maxRms, isGreenBoost
    );
    return synthesizeContinuousWSOLA(baseBuffer, pitchCurve, durCurve, wordIdxCurve, dt);
}

// ========================================================
// [운율 호흡구 그룹핑 및 통합 연속 사투리 발화]
// - isGreenBoost = false : 2번(하늘색) 순정 (demo_prosody.html 2번 버튼 100% 동일)
// - isGreenBoost = true  : 3번(초록색) 2번 엔진 + 어절 내 단음 강세 1.1~1.2배 연장 및 피치 보강
// ========================================================
const SKY_MAX_PHRASE_WORDS = 10;
const SKY_MIN_PHRASE_WORDS = 4;
const MODIFIER_NO_BREAK_WORDS = new Set([
    '이', '그', '저', '요', '고', '조', '한', '두', '세', '네', '온', '새', '맨',
    '참', '쫌', '좀', '더', '덜', '막', '다', '안', '앙', '못', '잘', '똑',
    '그레', '이레', '저레', '요레', '아주', '보통', '젤', '매우', '별로', '항상'
]);

function scoreProsodicBreakAfter(word) {
    if (!word || !word.syls || word.syls.length === 0) return 0;
    const lastSyl = word.syls[word.syls.length - 1];
    const punc = (lastSyl && lastSyl.punc) || "";
    const cleanWord = (word.raw || "").replace(/[^가-힣]/g, "");
    const collapsedWord = word.syls.map(s => s.collapsedChar || s.char).join("");

    let score = 0;
    // 1순위: 문장 내 쉼표·휴지 구두점
    if (/[,;…]/.test(punc)) {
        score += 100;
    } else if (/[~\)]/.test(punc)) {
        score += 75;
    }

    // 2순위: 경주 방언 연결어미 / 절 경계 (수식어 회피와 구분)
    if (/(니꺼네|니께네|지마는|거덩|거든|는데|은데|능데|니께|닝께|아가아|어가아|으머|면서|라꼬|다꼬|자꼬)$/.test(cleanWord) ||
        /(니꺼네|니께네|지마는|거덩|거든|는데|은데|능데|니께|닝께|으머|면서|라꼬|다꼬|자꼬)$/.test(collapsedWord)) {
        score += 65;
    } else if (cleanWord.length >= 2 && (/(가아|머|므|고|꼬)$/.test(cleanWord) || /(머|므|고|꼬)$/.test(collapsedWord))) {
        score += 45;
    } else if (cleanWord.length >= 2 && /(은|는|도|만|에는|에서는|까지)$/.test(collapsedWord)) {
        // 3순위: 긴 주어·부사구 뒤 조사 경계
        score += 20;
    }

    // 수식어·단음절 부사 바로 뒤는 의미가 끊어지므로 감점
    if (!punc && (MODIFIER_NO_BREAK_WORDS.has(collapsedWord) || MODIFIER_NO_BREAK_WORDS.has(cleanWord))) {
        score -= 55;
    }
    return score;
}

function splitLongSentenceIntoBalancedPhrases(sentWords) {
    const n = sentWords.length;
    if (n <= SKY_MAX_PHRASE_WORDS) return [sentWords];

    const numChunks = Math.ceil(n / SKY_MAX_PHRASE_WORDS);
    const minChunk = Math.min(SKY_MIN_PHRASE_WORDS, Math.floor(n / numChunks));
    const out = [];
    let start = 0;

    for (let c = 0; c < numChunks - 1; c++) {
        const remChunksAfter = numChunks - 1 - c;
        const minCut = Math.max(start + minChunk, n - remChunksAfter * SKY_MAX_PHRASE_WORDS);
        const maxCut = Math.min(start + SKY_MAX_PHRASE_WORDS, n - remChunksAfter * minChunk);
        const targetCut = start + (n - start) / (remChunksAfter + 1);

        let bestCut = Math.round(targetCut);
        bestCut = Math.max(minCut, Math.min(maxCut, bestCut));
        let bestScore = -Infinity;

        for (let cut = minCut; cut <= maxCut; cut++) {
            const boundaryScore = scoreProsodicBreakAfter(sentWords[cut - 1]);
            const balancePenalty = Math.abs(cut - targetCut) * 6;
            const total = boundaryScore - balancePenalty;
            if (total > bestScore) {
                bestScore = total;
                bestCut = cut;
            }
        }
        out.push(sentWords.slice(start, bestCut));
        start = bestCut;
    }
    if (start < n) out.push(sentWords.slice(start));
    return out;
}

function groupWordsIntoProsodicPhrases(words) {
    const sentences = [];
    let cur = [];

    for (let i = 0; i < words.length; i++) {
        const w = words[i];
        cur.push(w);

        const lastSyl = w.syls[w.syls.length - 1];
        const hasSentenceEnd = lastSyl && /[\.\?!]/.test(lastSyl.punc || "");

        // 1단계: 문장 종결부(. ? !) 단위로만 먼저 분리 (10어절 이하 문장은 통째로 유지)
        if (hasSentenceEnd || i === words.length - 1) {
            sentences.push(cur);
            cur = [];
        }
    }
    if (cur.length > 0) sentences.push(cur);

    // 2단계: 10어절을 초과하는 문장만 균형 + 쉼표/방언 연결어미 우선 위치로 분할
    const phrases = [];
    sentences.forEach(sent => {
        splitLongSentenceIntoBalancedPhrases(sent).forEach(p => phrases.push(p));
    });
    return phrases;
}

function playUnifiedDialectSpeechForSky(wordsList, params, myToken, isGreenBoost = false) {
    if (!window.speechSynthesis) return;

    const collapseLong = true;
    const shortAccentStretch = isGreenBoost ? getGreenShortAccentStretch() : 1.0;
    const maleVoice = getKoreanMaleVoice();
    const isExplicitMale = isExplicitMaleVoice(maleVoice);

    let pLow, pHigh, pEndHigh;

    if (isExplicitMale) {
        // 네이티브 남성 보이스(InJoon 등 ~120Hz)일 때: 평음·고음 구분 없이 기존 고음 피치 적용
        const pRefLow = Math.max(0.68, Math.min(0.95, 0.82 * (params.lowPitch / 1.05)));
        const gap = pRefLow * Math.max(0.48, (params.highPitch - 1.0) * 1.35);
        pHigh = Math.min(1.95, pRefLow + gap);
        pLow = pHigh;
        pEndHigh = Math.min(2.00, Math.max(pHigh + 0.08, pHigh * Math.pow(2, Math.max(0.5, params.endBoostSemitones) / 12.0)));
    } else {
        // 기본 여성 보이스(Microsoft Heami 등 ~225Hz): 평음·고음 구분 없이 기존 고음 피치 적용
        const pRefLow = Math.max(0.30, Math.min(0.42, 0.35 * (params.lowPitch / 1.05)));
        const gap = pRefLow * Math.max(0.55, (params.highPitch - 1.0) * 1.45);
        pHigh = Math.min(1.15, pRefLow + gap);
        pLow = pHigh;
        pEndHigh = Math.min(1.22, Math.max(pHigh + 0.06, pHigh * Math.pow(2, Math.max(0.5, params.endBoostSemitones) / 12.0)));
    }

    window.speechSynthesis.cancel();
    const utterances = [];

    wordsList.forEach((words) => {
        const phrases = groupWordsIntoProsodicPhrases(words);

        phrases.forEach((phraseWords) => {
            const phraseText = phraseWords.map(w => {
                return w.syls.map(s => {
                    return isGreenBoost
                        ? formatSyllableForGreenSpeech(s, params, collapseLong, shortAccentStretch)
                        : formatSyllableForSpeech(s, 'prosody', params, collapseLong);
                }).join('');
            }).join(' ').trim();
            if (!phraseText) return;

            const u = new SpeechSynthesisUtterance(phraseText);
            u.lang = 'ko-KR';
            if (maleVoice) u.voice = maleVoice;

            let totalSyls = 0;
            let highSyls = 0;
            let longSyls = 0;
            let shortHighSyls = 0;
            let firstSylHigh = false;
            let lastSylHigh = false;

            phraseWords.forEach((pw, pwIdx) => {
                pw.syls.forEach((s, sIdx) => {
                    totalSyls++;
                    if (s.tone === 'H') {
                        highSyls++;
                        if (!s.isLong) shortHighSyls++;
                    }
                    if (s.isLong) longSyls++;
                    if (pwIdx === 0 && sIdx === 0 && s.tone === 'H') firstSylHigh = true;
                    if (pwIdx === phraseWords.length - 1 && sIdx === pw.syls.length - 1 && s.tone === 'H') lastSylHigh = true;
                });
            });

            const highDensity = totalSyls > 0 ? (highSyls / totalSyls) : 0;
            const shortHighRatio = totalSyls > 0 ? (shortHighSyls / totalSyls) : 0;
            const isQuestionOrExclaim = /[\?\!]$/.test(phraseText.trim()) || /(애이가|인나|읻따|시더|디더|지요)[\.\?\!]*$/.test(phraseText.trim());

            // 평음·고음 구분 없이 기존 고음 기본 피치(pHigh)로 통합 적용
            let targetPitch = pHigh;
            if (isGreenBoost && shortHighSyls > 0) {
                const greenPitchExtra = Math.min(0.18, (shortAccentStretch - 1.0) * (0.65 + shortHighRatio * 0.35));
                targetPitch = pHigh + greenPitchExtra;
            }
            if (isQuestionOrExclaim) {
                targetPitch = Math.max(targetPitch, pEndHigh * (isGreenBoost ? 1.04 : 1.0));
            }
            u.pitch = Number(Math.max(0.2, Math.min(2.0, targetPitch)).toFixed(2));

            // 장모음 및 3번(초록색) 단음 강세 연장 감속 계산
            let phraseRate = params.baseRate;
            if (longSyls > 0) {
                const longRatio = longSyls / Math.max(1, totalSyls);
                let slowFactor = 1.0 + (params.longStretch - 1.0) * (0.16 + longRatio * 0.14);
                if (isGreenBoost && shortHighSyls > 0) {
                    slowFactor += Math.max(0, shortAccentStretch - 1.0) * (0.55 + shortHighRatio * 0.45);
                }
                phraseRate = params.baseRate / slowFactor;
            } else if (isGreenBoost && shortHighSyls > 0) {
                // 3번(초록색): 장모음이 없더라도 단음 강세 음절이 포함된 경우 약 1.1~1.2배 길어지도록 속도 여유 부여
                const shortSlowFactor = 1.0 + Math.max(0, shortAccentStretch - 1.0) * (0.75 + shortHighRatio * 0.45);
                phraseRate = params.baseRate / shortSlowFactor;
            } else if (highSyls === 0) {
                // 평조 단모음 구간은 자연스러운 대화 속도로 경쾌하게 연결
                phraseRate = params.baseRate * 1.05;
            }
            u.rate = Number(Math.max(0.58, Math.min(1.30, phraseRate)).toFixed(2));

            utterances.push(u);
        });
    });

    if (utterances.length === 0) return;

    setTimeout(() => {
        if (myToken !== skySpeakToken) return;
        utterances.forEach(u => window.speechSynthesis.speak(u));
    }, 50);
}

// 2번(하늘색) 및 3번(초록색) 공통 실행 파이프라인
async function runContinuousDialectTTS(rawText, isGreenBoost = false) {
    if (!rawText) return;
    stopSkyProsodyAudio();
    const myToken = skySpeakToken;

    // 1번(파란색) 오디오가 재생 중이면 겹치지 않게 정지
    if (window.currentAudio) {
        try { window.currentAudio.pause(); } catch (e) {}
        window.currentAudio = null;
    }

    let text = rawText.trim();
    if (text.startsWith('[') && text.endsWith(']')) {
        text = text.slice(1, -1).trim();
    }
    text = text.replace(/\[(.*?)\]/g, ' $1 ');
    text = text.replace(/\{([^/>-]+)[/>-][^}]+\}/g, '$1');
    text = text.replace(/<[^>]+>/g, '');
    text = text.replace(/°/g, '');

    const params = getSkyProsodyParams();
    const collapseLong = true;

    // '/'로 구분된 복수 발음 각각 파싱
    const parts = text.split('/').map(p => p.trim()).filter(Boolean);
    const wordsList = parts.map(p => parseDialectSentenceForSpeech(p)).filter(w => w.length > 0);
    if (wordsList.length === 0) return;

    // 1. 로컬 Praat edge_server.py 확인 (실행 중일 때 최우선 재생 + 무단절 WSOLA 장모음/성조 변조 적용)
    try {
        const allWords = wordsList.flat();
        const wsolaText = allWords.map(w => w.syls.map(s => (collapseLong && s.isLong ? s.collapsedChar : s.rawPair) + s.punc).join('')).join(' ');
        const baseBuffer = await fetchContinuousSentenceBuffer(wsolaText);
        if (myToken !== skySpeakToken) return;
        if (baseBuffer) {
            const { outBuffer } = synthesizeContinuousProsodyBuffer(baseBuffer, allWords, params, isGreenBoost);
            const ctx = getSkyAudioContext();
            const src = ctx.createBufferSource();
            src.buffer = outBuffer;
            src.connect(ctx.destination);
            skyCurrentSourceNode = src;
            src.onended = () => {
                if (skyCurrentSourceNode === src) skyCurrentSourceNode = null;
            };
            src.start();
            return;
        }
    } catch (e) {}

    if (myToken !== skySpeakToken) return;

    // 2. 통합 브라우저 음성 합성 엔진
    playUnifiedDialectSpeechForSky(wordsList, params, myToken, isGreenBoost);
}

// 2번 하늘색 스피커 발화 함수 (demo_prosody.html의 2번 버튼 100% 동일)
async function speakDialectWebSpeechQuestion(rawText) {
    return runContinuousDialectTTS(rawText, false);
}

// 3번 초록색 스피커 발화 함수 (2번 엔진 + 어절 내 단음 강세 1.1~1.2배 길이 연장 및 피치 보강)
async function speakDialectWebSpeechGreen(rawText) {
    return runContinuousDialectTTS(rawText, true);
}

// [설화 리더 오디오북용 Promise 래퍼]
// WSOLA 또는 Web Speech API 발화가 끝날 때까지 대기 (정지/토큰 변경 시 즉시 resolve(false))
function speakDialectSentenceAsync(rawText, isGreenBoost = false) {
    return new Promise((resolve) => {
        if (!rawText) { resolve(false); return; }
        stopSkyProsodyAudio();
        const myToken = skySpeakToken;

        let text = rawText.trim();
        if (text.startsWith('[') && text.endsWith(']')) {
            text = text.slice(1, -1).trim();
        }
        text = text.replace(/\[(.*?)\]/g, '  ');
        text = text.replace(/\{([^/>-]+)[/>-]+[^}]+\}/g, '');
        text = text.replace(/<[^>]+>/g, '');
        text = text.replace(/°/g, '');

        const params = getSkyProsodyParams();
        const collapseLong = true;
        const parts = text.split('/').map(p => p.trim()).filter(Boolean);
        const wordsList = parts.map(p => parseDialectSentenceForSpeech(p)).filter(w => w.length > 0);
        if (wordsList.length === 0) { resolve(true); return; }

        (async () => {
            try {
                const allWords = wordsList.flat();
                const wsolaText = allWords.map(w => w.syls.map(s => (collapseLong && s.isLong ? s.collapsedChar : s.rawPair) + s.punc).join('')).join(' ');
                const baseBuffer = await fetchContinuousSentenceBuffer(wsolaText);
                if (myToken !== skySpeakToken) { resolve(false); return; }
                if (baseBuffer) {
                    const { outBuffer } = synthesizeContinuousProsodyBuffer(baseBuffer, allWords, params, isGreenBoost);
                    const ctx = getSkyAudioContext();
                    const src = ctx.createBufferSource();
                    src.buffer = outBuffer;
                    src.connect(ctx.destination);
                    skyCurrentSourceNode = src;
                    src.onended = () => {
                        if (skyCurrentSourceNode === src) skyCurrentSourceNode = null;
                        resolve(myToken === skySpeakToken);
                    };
                    src.start();
                    return;
                }
            } catch (e) {}

            if (myToken !== skySpeakToken) { resolve(false); return; }

            // Web Speech fallback with completion tracking
            if (!window.speechSynthesis) { resolve(false); return; }
            window.speechSynthesis.cancel();
            const maleVoice = getKoreanMaleVoice();
            const isExplicitMale = isExplicitMaleVoice(maleVoice);
            const pHigh = isExplicitMale ? 1.18 : 0.72;
            const pEndHigh = isExplicitMale ? 1.24 : 0.78;
            const shortAccentStretch = isGreenBoost ? getGreenShortAccentStretch() : 1.0;

            const utterances = [];
            wordsList.forEach((words) => {
                words.forEach((w) => {
                    const phrase = w.syls.map(s =>
                        isGreenBoost
                            ? formatSyllableForGreenSpeech(s, params, true, shortAccentStretch)
                            : formatSyllableForSpeech(s, 'prosody', params, true)
                    ).join('');
                    const totalSyls = w.syls.length;
                    const highSyls = w.syls.filter(s => s.tone === 'H').length;
                    const longSyls = w.syls.filter(s => s.isLong).length;
                    const shortHighSyls = w.syls.filter(s => !s.isLong && s.tone === 'H').length;
                    const shortHighRatio = shortHighSyls / Math.max(1, totalSyls);
                    const isQ = /[?!]/.test(phrase);

                    const u = new SpeechSynthesisUtterance(phrase);
                    u.lang = 'ko-KR';
                    if (maleVoice) u.voice = maleVoice;

                    let targetPitch = pHigh;
                    if (isGreenBoost && shortHighSyls > 0) {
                        targetPitch = pHigh + Math.min(0.18, (shortAccentStretch - 1.0) * (0.65 + shortHighRatio * 0.35));
                    }
                    if (isQ) targetPitch = Math.max(targetPitch, pEndHigh * (isGreenBoost ? 1.04 : 1.0));
                    u.pitch = Number(Math.max(0.2, Math.min(2.0, targetPitch)).toFixed(2));

                    let phraseRate = params.baseRate;
                    if (longSyls > 0) {
                        const longRatio = longSyls / Math.max(1, totalSyls);
                        let slowFactor = 1.0 + (params.longStretch - 1.0) * (0.16 + longRatio * 0.14);
                        if (isGreenBoost && shortHighSyls > 0) {
                            slowFactor += Math.max(0, shortAccentStretch - 1.0) * (0.55 + shortHighRatio * 0.45);
                        }
                        phraseRate = params.baseRate / slowFactor;
                    } else if (isGreenBoost && shortHighSyls > 0) {
                        const shortSlowFactor = 1.0 + Math.max(0, shortAccentStretch - 1.0) * (0.75 + shortHighRatio * 0.45);
                        phraseRate = params.baseRate / shortSlowFactor;
                    } else if (highSyls === 0) {
                        phraseRate = params.baseRate * 1.05;
                    }
                    u.rate = Number(Math.max(0.58, Math.min(1.30, phraseRate)).toFixed(2));
                    utterances.push(u);
                });
            });

            if (utterances.length === 0) { resolve(true); return; }

            let finished = false;
            const done = (ok) => {
                if (!finished) { finished = true; resolve(ok); }
            };
            utterances[utterances.length - 1].onend = () => done(myToken === skySpeakToken);
            utterances[utterances.length - 1].onerror = () => done(false);

            // Token watcher in case user stops mid-sentence
            const watcher = setInterval(() => {
                if (myToken !== skySpeakToken) {
                    clearInterval(watcher);
                    done(false);
                } else if (finished) {
                    clearInterval(watcher);
                }
            }, 100);

            setTimeout(() => {
                if (myToken !== skySpeakToken) { done(false); return; }
                utterances.forEach(u => window.speechSynthesis.speak(u));
            }, 40);
        })();
    });
}
