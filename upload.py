# -*- coding: utf-8 -*-
"""
楽天ブログ自動投稿（GitHub Actions用）
Google Driveからダウンロード → ランダム1ファイル → Playwrightで楽天ブログに投稿
※ 楽天ブログにはAPIがないため、ブラウザ自動操作で投稿する
"""
import sys, json, os, random, time, re, shutil
from pathlib import Path

import requests
import gdown


def safe_screenshot(page, path, timeout=10000):
    """Take a debug screenshot, ignoring errors so it never breaks the main flow."""
    try:
        page.screenshot(path=path, timeout=timeout)
    except Exception as e:
        print(f"  (screenshot skipped: {e})")

# ============================================================
# 設定
# ============================================================

GDRIVE_FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID", "")
RAKUTEN_USER_ID = os.environ.get("RAKUTEN_USER_ID", "")
RAKUTEN_PASSWORD = os.environ.get("RAKUTEN_PASSWORD", "")
RAKUTEN_BLOG_ID = os.environ.get("RAKUTEN_BLOG_ID", "")  # plaza.rakuten.co.jp/{BLOG_ID}/

PATREON_LINK = "https://www.patreon.com/cw/MuscleLove?utm_source=rakuten"
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 楽天写真館上限: 20MB
UPLOADED_LOG = "uploaded.json"
MEDIA_DIR = Path("media")
PREPARED_DIR = Path("prepared_media")

# --- MuscleLove バックリンクプール（フィットネス系のみ。一般プラットフォーム配慮） ---
ML_BACKLINK_POOL_FITNESS = [
    ("https://musclelove-777.github.io/muscle-meal-girls/", "筋肉女子のマッスルメシ"),
    ("https://musclelove-777.github.io/runners-lab/", "ランナーラボ"),
    ("https://musclelove-777.github.io/armwrestling-girls-navi/", "腕相撲女子ナビ"),
    ("https://musclelove-777.github.io/physique-girls-navi/", "フィジーク女子ナビ"),
    ("https://musclelove-777.github.io/fighting-girls-navi/", "格闘技女子ナビ"),
    ("https://musclelove-777.github.io/joshi-prowrestling-navi/", "女子プロレスナビ"),
    ("https://musclelove-777.github.io/female-physique-queens/", "Female Physique Queens"),
    ("https://musclelove-777.github.io/network/fitness/", "全Fitness Network 15サイト一覧"),
    ("https://musclelove-777.github.io/network/academy/", "MuscleLove Academy 77サイト"),
]


def build_backlink_block():
    """MuscleLoveフィットネス系サイトへのバックリンクHTMLブロック（ランダム3件、冪等マーカー付き）"""
    try:
        k = min(3, len(ML_BACKLINK_POOL_FITNESS))
        selected = random.sample(ML_BACKLINK_POOL_FITNESS, k=k)
        items = " | ".join([f'<a href="{u}" target="_blank" rel="noopener">{n}</a>' for u, n in selected])
        return (
            "\n<br/><br/>\n"
            "<!-- ML_BACKLINK -->\n"
            f'<small style="color:#888;">💡 関連サイト：{items}</small>\n'
            "<!-- /ML_BACKLINK -->\n"
        )
    except Exception:
        return ""

# ============================================================
# 記事タイトルテンプレート（人気ブログ風）
# ============================================================
TITLE_TEMPLATES = [
    "【衝撃】この筋肉美、見たことある？",
    "【保存版】筋肉女子の美しさがヤバすぎる件",
    "【圧巻】鍛え抜かれた身体がここに",
    "【必見】こんな筋肉美、他にない",
    "【驚愕】女性の筋肉美ここに極まれり",
    "今日出会った最高の筋肉美を紹介する",
    "この鍛え上げた身体、反則でしょ...",
    "筋肉女子の魅力が止まらない件について",
    "見てくれ、この圧倒的な肉体美を",
    "これが本物のフィットネスボディ",
    "もうね、この筋肉に惚れた（直球）",
    "筋肉女子の破壊力がエグい",
    "バキバキボディの美しさを語りたい",
    "今日の筋肉女子が最高すぎたｗ",
    "鍛え抜いた身体って、なんでこんなに美しいの",
    "【Muscle Queen】今日のベストショット",
    "【Strong is Beautiful】鍛えた女性は美しい",
    "【Iron Goddess】圧倒的筋肉美",
    "【Power & Beauty】強さと美しさの共存",
    "筋肉女子の魅力、あなたは気づいてる？",
    "なぜ鍛えた女性はこんなに美しいのか",
    "筋トレ女子を推さない理由がない",
]

# ============================================================
# ブログ記事テンプレート（MuscleLove文体 × 人気ブログ構成）
# ============================================================
BLOG_BODY_TEMPLATES = [
    # テンプレ1: カジュアル・興奮系
    {
        'opening': [
            'どうも、MuscleLoveです💪',
            'やっほー、MuscleLoveやで💪',
            'MuscleLoveです！今日もいくぞ🔥',
        ],
        'intro': [
            'いやー、今日もヤバいの見つけてしまった。',
            '今日の一枚、マジでやばい。語彙力失うレベル。',
            'はい来ました。これは保存確定ですわ。',
            'もうね、こういうの見ると元気出るよね。',
        ],
        'body': [
            'この引き締まった身体、見てくれよ。\n'
            '鍛え上げた筋肉の一つ一つが美しい。\n'
            'こういう肉体美って、日々の努力の結晶なんだよな。',
            'バキバキに仕上がった身体。\n'
            '筋肉のカット、ポージング、全部が芸術。\n'
            'これぞ鍛え抜いた者だけが持てる美しさ。',
            '迫力ある筋肉美と色気あふれるポーズ。\n'
            '汗ばむ肌と浮き出る筋肉のコントラストがたまらん。\n'
            '強さと美しさって共存するんだよな。',
        ],
        'closing': [
            'やっぱ筋肉女子は最高だわ（確信）',
            'これだから筋肉女子の推し活はやめられない',
            '今日もいい筋肉を見て、いい1日だった',
        ],
    },
    # テンプレ2: 解説・豆知識系
    {
        'opening': [
            'MuscleLoveです！',
            'こんにちは、MuscleLoveです✨',
        ],
        'intro': [
            '今日は筋肉美の魅力について語りつつ、最高の一枚を紹介します。',
            '筋トレ女子の美しさ、伝わってますか？今日も全力で紹介します。',
            '鍛えた女性の身体って本当に美しい。今日もその魅力をお届け。',
        ],
        'body': [
            '■ 筋肉女子が美しい理由\n\n'
            '鍛え上げた筋肉には、日々のストイックな努力が詰まってる。\n'
            '食事管理、トレーニング、休息のバランス。\n'
            'その全てが身体に表れるから、こんなに美しいんだよな。\n\n'
            '今日の一枚も、まさにその結晶。',
            '■ なぜ筋肉美に惹かれるのか\n\n'
            '筋肉って「努力の可視化」なんだよね。\n'
            '毎日のトレーニングが、そのまま身体のラインに出る。\n'
            '嘘がつけない。だから美しい。\n\n'
            '今日のショットも、その美しさが詰まってる。',
        ],
        'closing': [
            '筋肉女子の魅力、少しでも伝わったら嬉しい！',
            '鍛えた身体の美しさ、これからも発信していくよ💪',
            'もっと筋肉女子の世界を知りたい人は、ぜひ見てって！',
        ],
    },
    # テンプレ3: ストーリー・シチュエーション系
    {
        'opening': [
            'MuscleLoveです🔥',
            'どうも！MuscleLoveです💪',
        ],
        'intro': [
            'ある日のジムにて。こんな光景に出会ったら、目が離せなくなるよな。',
            '今日は特別な一枚。この筋肉美、ストーリーを感じない？',
            '想像してみてくれ。目の前にこの肉体美があったら。',
        ],
        'body': [
            '鍛え抜かれた身体から放たれるオーラ。\n'
            '一つ一つの筋肉が語りかけてくるような迫力。\n'
            'これだけのフィジークを作り上げるには、\n'
            '想像を超える努力があったはず。\n\n'
            'それでも彼女たちは笑顔で、軽々とポーズを決める。\n'
            'かっこよすぎないか...？',
            'この身体を見てほしい。\n'
            'シュレッドされた腹筋、盛り上がった肩、引き締まった脚。\n'
            '全てが完璧なバランスで仕上がってる。\n\n'
            'こういう肉体美を見ると、\n'
            '「人間の身体ってここまでいけるんだ」って感動するよな。',
        ],
        'closing': [
            'こういう出会いがあるから、筋肉女子の世界はやめられない',
            '最高の筋肉美をお届けできたかな？',
            '今日もいい筋肉に出会えた。感謝。',
        ],
    },
    # テンプレ4: 超短文・テンポ系（モバイル向き）
    {
        'opening': [
            'MuscleLove💪',
            '🔥MuscleLove🔥',
        ],
        'intro': [
            'はい、今日のベストショット。',
            '見てくれ。',
            '今日の一枚。',
        ],
        'body': [
            'この筋肉。\nこの迫力。\nこの美しさ。\n\n語彙力？いらん。見ればわかる。',
            'バキバキ。\nシュレッド。\nパーフェクト。\n\n以上。（褒め言葉）',
            '強い。\n美しい。\n最高。\n\n筋肉女子、推すしかない。',
        ],
        'closing': [
            'はい優勝🏆',
            '今日も筋肉に感謝✨',
            '以上！また明日💪',
        ],
    },
    # テンプレ5: 問いかけ・読者参加系
    {
        'opening': [
            'MuscleLoveです！今日はみんなに聞きたいことがある💪',
            'こんにちは、MuscleLoveです！',
        ],
        'intro': [
            '突然だけど、筋肉女子の魅力って何だと思う？',
            'あなたが筋肉女子に惹かれるポイント、どこ？',
            '今日はこの写真を見て、率直な感想を聞かせてほしい。',
        ],
        'body': [
            '俺はね、やっぱりこの「鍛え抜いた感」がたまらないんよ。\n\n'
            '腹筋のカット、肩のキャップ、背中の広がり。\n'
            '全部が努力の証。\n'
            'その覚悟と結果が身体に刻まれてるのが、最高にかっこいい。\n\n'
            'あなたはどう思う？',
            '筋肉美の魅力って人それぞれだと思うんだけど、\n'
            '俺が好きなのはこの「ストイックさが身体に出てる」ところ。\n\n'
            '甘えなし、言い訳なし。\n'
            'ただひたすら鍛え上げた結果がこれ。\n'
            '美しくない？',
        ],
        'closing': [
            'コメントで教えてくれ！筋肉女子のどこが好き？💪',
            'あなたの推しポイント、コメントで語ろう🔥',
            'みんなの意見聞かせて！',
        ],
    },
]

# ハッシュタグ
BASE_HASHTAGS = [
    '筋トレ', '筋肉女子', 'フィットネス', 'ワークアウト', 'ジム',
    'musclegirl', 'fitness', 'strongwomen', 'workout', 'gym',
    'MuscleLove', 'FBB', 'fitnessmotivation', '筋トレ女子',
    '筋肉美', 'マッスルガール', 'フィジーク',
]

CONTENT_TAG_MAP = {
    'training': ['筋トレ', 'トレーニング', 'workout'],
    'workout': ['筋トレ', 'ワークアウト', 'gym'],
    'pullups': ['懸垂', '背中トレ', 'pullups'],
    'posing': ['ポージング', 'ボディビル', 'posing'],
    'flex': ['フレックス', '筋肉', 'flex'],
    'muscle': ['筋肉', 'マッスル', 'muscle'],
    'bicep': ['上腕二頭筋', '腕トレ', 'biceps'],
    'abs': ['腹筋', 'シックスパック', 'abs'],
    'leg': ['脚トレ', 'レッグデイ', 'legs'],
    'back': ['背中', 'ラット', 'back'],
    'squat': ['スクワット', '脚トレ', 'squat'],
}


# ============================================================
# アップロード済み管理
# ============================================================

def load_uploaded_log():
    if not os.path.exists(UPLOADED_LOG):
        return {"files": []}
    with open(UPLOADED_LOG, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if isinstance(data, list):
        return {"files": data}
    return data


def save_uploaded_log(log_data):
    with open(UPLOADED_LOG, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)


def used_source_keys(log_data):
    used = set()
    for entry in log_data.get("files", []):
        if not isinstance(entry, dict):
            continue
        for key in ("source_key", "source_name", "file"):
            value = entry.get(key)
            if value:
                used.add(str(value))
    return used


# ============================================================
# Google Driveダウンロード
# ============================================================

def download_media():
    if MEDIA_DIR.exists():
        shutil.rmtree(MEDIA_DIR)
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    url = f"https://drive.google.com/drive/folders/{GDRIVE_FOLDER_ID}"
    print(f"Downloading from Google Drive: {url}")
    try:
        gdown.download_folder(url, output=str(MEDIA_DIR), quiet=False, remaining_ok=True, use_cookies=False)
    except TypeError:
        gdown.download_folder(url, output=str(MEDIA_DIR), quiet=False, remaining_ok=True)
    except Exception as e:
        print(f"Download error: {e}")

    files = []
    for root, dirs, filenames in os.walk(MEDIA_DIR):
        for fname in filenames:
            fpath = os.path.join(root, fname)
            ext = os.path.splitext(fname)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                size = os.path.getsize(fpath)
                if size <= MAX_FILE_SIZE:
                    source_key = Path(fpath).relative_to(MEDIA_DIR).as_posix()
                    files.append({
                        "path": fpath,
                        "source_key": source_key,
                        "source_name": fname,
                    })
                else:
                    print(f"Skip (>20MB): {fname} ({size / 1024 / 1024:.1f}MB)")
    return files


def select_media(media_files, log_data):
    """未使用素材からランダム選択。全消化済みなら全体からリサイクル。"""
    if not media_files:
        return None, []

    used = used_source_keys(log_data)
    available = [
        item for item in media_files
        if item["source_key"] not in used and item["source_name"] not in used
    ]
    if not available:
        print("All Drive images already used. Recycling full pool.")
        available = list(media_files)

    rng = random.SystemRandom()
    rng.shuffle(available)
    selected = rng.choice(available)
    return selected, available


def prepare_image_for_rakuten(image_path):
    """楽天写真館向けにJPEGへ正規化し、20MB未満に収める。"""
    from PIL import Image

    PREPARED_DIR.mkdir(parents=True, exist_ok=True)
    src = Path(image_path)
    out = PREPARED_DIR / f"{src.stem}_rakuten.jpg"

    with Image.open(src) as img:
        img = img.convert("RGB")
        # 楽天側の失敗を避けるため、長辺をやや抑えてJPEG化する
        img.thumbnail((1800, 2400), Image.Resampling.LANCZOS)

        quality = 92
        while quality >= 72:
            img.save(out, format="JPEG", quality=quality, optimize=True)
            if out.stat().st_size <= MAX_FILE_SIZE:
                print(f"Prepared JPEG: {out} ({out.stat().st_size / 1024 / 1024:.1f}MB, q={quality})")
                return str(out)
            quality -= 5

    raise RuntimeError(f"Prepared image is still too large: {out}")


# ============================================================
# タグ・記事生成
# ============================================================

def generate_tags(file_path):
    tags = list(BASE_HASHTAGS)
    path_lower = file_path.lower().replace('\\', '/').replace('-', ' ').replace('_', ' ')
    matched = set()
    for keyword, keyword_tags in CONTENT_TAG_MAP.items():
        if keyword in path_lower:
            for t in keyword_tags:
                if t not in matched:
                    tags.append(t)
                    matched.add(t)
    seen = set()
    unique = []
    for t in tags:
        if t.lower() not in seen:
            seen.add(t.lower())
            unique.append(t)
    return unique


def sanitize_category(name, max_len=30):
    name = re.sub(r'[{}\[\]]', '', name)
    if ',' in name:
        name = name.split(',')[0].strip()
    name = name.strip(' -_')
    if len(name) > max_len:
        name = name[:max_len].rstrip(' -_')
    return name if name else "Muscle"


def build_blog_html(image_url, tags, file_path):
    """記事のタイトルとHTML本文を生成（TinyMCE直接挿入用）"""
    parts = file_path.replace('\\', '/').split('/')
    category = "Muscle"
    for p in parts:
        if p not in ['media', ''] and '.' not in p:
            category = sanitize_category(p)
            break

    # タイトル
    title = random.choice(TITLE_TEMPLATES)

    # テンプレート選択
    template = random.choice(BLOG_BODY_TEMPLATES)
    opening = random.choice(template['opening'])
    intro = random.choice(template['intro'])
    body = random.choice(template['body'])
    closing = random.choice(template['closing'])

    hashtag_text = ' '.join([f'#{t}' for t in tags[:15]])

    # HTML形式で本文を生成（TinyMCEに直接挿入する）
    body_html = body.replace('\n', '<br>')

    content_html = f'''<p>{opening}</p>
<p>{intro}</p>
<p>&nbsp;</p>
<div style="text-align: center;">
<img src="{image_url}" alt="{category}" style="max-width: 100%;" />
</div>
<p>&nbsp;</p>
<p>{body_html}</p>
<p>&nbsp;</p>
<p>{closing}</p>
<hr />
<div style="text-align: center; background: #1a1a2e; padding: 20px; border-radius: 10px; margin: 20px 0;">
<p style="font-size: 1.3em; color: #FFD700;">🔥 もっと見たい？ Patreonで限定コンテンツ公開中！</p>
<p style="font-size: 1.1em;"><a href="{PATREON_LINK}" target="_blank" rel="noopener" style="color: #00C9FF; text-decoration: underline;">👉 MuscleLove on Patreon 👈</a></p>
<p style="font-size: 0.9em; color: #ccc;">ここでしか見れない筋肉美をお届け中💪</p>
</div>
<p>&nbsp;</p>
<p style="color: #888; font-size: 0.85em;">{hashtag_text}</p>'''

    content_html = content_html.rstrip() + build_backlink_block()
    return title, content_html


# ============================================================
# Playwright: 楽天ブログに投稿
# ============================================================

RAKUTEN_IMAGE_RE = re.compile(
    r'https://image\.space\.rakuten\.co\.jp/d/strg/ctrl/\d+/[a-f0-9]+\.\d+\.\d+\.\d+\.\d+\.\w+'
)

def _rakuten_login(page):
    """楽天ログイン処理（共通）"""
    if 'grp' in page.url or 'login' in page.url.lower() or 'nid' in page.url:
        print("  Login required...")
        try:
            user_input = page.locator('input[type="text"]:visible, input[type="email"]:visible').first
            user_input.fill(RAKUTEN_USER_ID)
            print(f"  User ID filled: {RAKUTEN_USER_ID[:3]}***")
            time.sleep(1)
            page.locator('button:visible:has-text("次へ"), input[type="submit"]:visible').first.click()
            print("  Next clicked")
            time.sleep(3)
        except Exception as e:
            print(f"  User ID step: {e}")

        try:
            pass_input = page.locator('input[type="password"]:visible').first
            pass_input.wait_for(state='visible', timeout=10000)
            pass_input.fill(RAKUTEN_PASSWORD)
            print("  Password filled")
            time.sleep(1)
            page.locator('button:visible:has-text("ログイン"), input[type="submit"]:visible').first.click()
            print("  Login clicked")
            time.sleep(5)
        except Exception as e:
            print(f"  Password step: {e}")

        print(f"  After login: {page.url}")
    else:
        print("  Already logged in")


def collect_rakuten_image_urls(page):
    """楽天写真館ページ内の画像URLを重複なし・表示順で取得する。"""
    urls = page.evaluate('''() => {
        const found = [];
        const push = (value) => {
            if (!value) return;
            if (value.includes('image.space.rakuten') && value.includes('/strg/')) {
                found.push(value);
            }
        };
        document.querySelectorAll('img').forEach(img => {
            push(img.currentSrc || img.src || img.getAttribute('src'));
        });
        document.querySelectorAll('a[href], input[value], textarea').forEach(el => {
            push(el.getAttribute('href'));
            push(el.getAttribute('value'));
            push(el.value);
            push(el.textContent);
        });
        return found;
    }''')

    html = page.content()
    urls.extend(RAKUTEN_IMAGE_RE.findall(html))

    unique = []
    seen = set()
    for url in urls:
        if not url:
            continue
        clean = str(url).strip()
        if clean in seen:
            continue
        seen.add(clean)
        unique.append(clean)
    return unique


def upload_image_to_rakuten(page, image_path):
    """画像管理ページで画像をアップロードし、画像URLを返す"""
    print(f"  Uploading: {os.path.basename(image_path)}")

    # 画像管理ページへ
    page.goto('https://my.plaza.rakuten.co.jp/image/list/',
               wait_until='domcontentloaded', timeout=30000)
    time.sleep(3)
    _rakuten_login(page)
    if 'image/list' not in page.url:
        page.goto('https://my.plaza.rakuten.co.jp/image/list/',
                   wait_until='domcontentloaded', timeout=30000)
        time.sleep(3)

    before_urls = set(collect_rakuten_image_urls(page))
    print(f"  Existing Rakuten images before upload: {len(before_urls)}")

    # アップロードボタンをクリック
    uploaded_clicked = False
    try:
        page.locator('a.imgListUpload').first.click()
        time.sleep(3)
        safe_screenshot(page, 'debug_upload_modal.png')

        # colorbox内のファイル入力を探す。非表示inputでもDOMにあればset_input_filesできる。
        file_input = page.locator('#cboxLoadedContent input[type="file"], input[type="file"]').first
        file_input.wait_for(state='attached', timeout=10000)
        file_input.set_input_files(image_path)
        print("  File selected")
        time.sleep(3)

        # アップロード実行ボタン
        for sel in ['button:has-text("アップロード")', 'input[value*="アップロード"]',
                    'button:has-text("OK")', 'a:has-text("アップロード")']:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=3000):
                    btn.click()
                    print(f"  Upload clicked: {sel}")
                    uploaded_clicked = True
                    time.sleep(8)
                    break
            except Exception:
                continue
    except Exception as e:
        print(f"  Upload modal approach failed: {e}")

    if not uploaded_clicked:
        print("  Warning: upload submit button was not confirmed")
        try:
            file_input = page.locator('input[type="file"]').first
            file_input.wait_for(state='attached', timeout=5000)
            file_input.set_input_files(image_path)
            print("  Fallback file selected")
            page.keyboard.press("Enter")
            time.sleep(8)
        except Exception as e:
            print(f"  Fallback upload failed: {e}")

    # 画像一覧を再読み込みして最新の画像URLを取得
    page.goto('https://my.plaza.rakuten.co.jp/image/list/',
               wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)

    image_urls = collect_rakuten_image_urls(page)
    new_urls = [u for u in image_urls if u not in before_urls]

    if new_urls:
        url = new_urls[0]
        print(f"  New image URL: {url[:80]}...")
        return url
    elif image_urls:
        # 楽天側の一覧DOMが差分を出さない場合の保険。重複投稿を避けるためメイン側でログ管理する。
        url = image_urls[0]
        print(f"  Warning: no new URL detected; fallback to first listed image: {url[:80]}...")
        return url
    else:
        print("  Warning: No image URLs found")
        return None


def get_existing_image_url(page):
    """既存のアップロード済み画像からランダムに1つURLを取得"""
    page.goto('https://my.plaza.rakuten.co.jp/image/list/',
               wait_until='domcontentloaded', timeout=30000)
    time.sleep(3)
    _rakuten_login(page)
    if 'image/list' not in page.url:
        page.goto('https://my.plaza.rakuten.co.jp/image/list/',
                   wait_until='domcontentloaded', timeout=30000)
        time.sleep(3)

    return collect_rakuten_image_urls(page)


def post_to_rakuten_blog(image_url, title, content_html):
    """Playwrightで楽天ブログにログイン → 記事投稿
    image_url: 楽天写真館の画像URL（既にアップロード済み）
    content_html: 画像imgタグを含むHTML本文
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 900},
        )

        cookie_file = 'rakuten_cookies.json'
        if os.path.exists(cookie_file):
            with open(cookie_file, 'r') as f:
                cookies = json.load(f)
            context.add_cookies(cookies)
            print("Loaded saved cookies")

        page = context.new_page()

        try:
            # ============================================
            # Step 1: 日記作成ページへ（ログイン含む）
            # ============================================
            print("Step 1: Navigating to diary write page...")
            page.goto('https://my.plaza.rakuten.co.jp/diary/write/',
                       wait_until='domcontentloaded', timeout=30000)
            time.sleep(3)
            _rakuten_login(page)

            if 'diary/write' not in page.url:
                page.goto('https://my.plaza.rakuten.co.jp/diary/write/',
                           wait_until='domcontentloaded', timeout=30000)
                time.sleep(3)

            page.locator('#diary_write_d_title').wait_for(state='visible', timeout=10000)
            print(f"  Diary write page ready")
            safe_screenshot(page, 'debug_diarywrite.png')

            # ============================================
            # Step 2: タイトル入力
            # ============================================
            print(f"Step 2: Title: {title}")
            page.locator('#diary_write_d_title').fill(title)

            # ============================================
            # Step 3: 本文入力（TinyMCEに直接HTML挿入）
            # ============================================
            print("Step 3: Inserting content into TinyMCE...")

            result = page.evaluate('''(html) => {
                const editor = window.tinymce && window.tinymce.get && window.tinymce.get('diary_write_d_text');
                if (editor) {
                    editor.setContent(html);
                    editor.save();
                    editor.fire('change');
                    return 'success:tinymce';
                }

                const iframe = document.getElementById('diary_write_d_text_ifr');
                if (iframe && iframe.contentDocument) {
                    iframe.contentDocument.body.innerHTML = html;
                    iframe.contentDocument.body.dispatchEvent(new Event('input', {bubbles: true}));
                    iframe.contentDocument.body.dispatchEvent(new Event('change', {bubbles: true}));
                    const textarea = document.getElementById('diary_write_d_text');
                    if (textarea) {
                        textarea.value = html;
                        textarea.dispatchEvent(new Event('input', {bubbles: true}));
                        textarea.dispatchEvent(new Event('change', {bubbles: true}));
                    }
                    return 'success:iframe';
                }
                return 'iframe not found';
            }''', content_html)
            print(f"  TinyMCE insert: {result}")

            if not str(result).startswith('success'):
                # フォールバック: frame_locator経由
                try:
                    iframe = page.frame_locator('#diary_write_d_text_ifr')
                    body_el = iframe.locator('body')
                    body_el.wait_for(state='visible', timeout=5000)
                    body_el.evaluate(f'(el) => {{ el.innerHTML = {json.dumps(content_html)}; }}')
                    print("  Content filled via frame_locator fallback")
                except Exception as e:
                    print(f"  Fallback also failed: {e}")

            safe_screenshot(page, 'debug_content.png')

            inserted_html = page.evaluate('''() => {
                const editor = window.tinymce && window.tinymce.get && window.tinymce.get('diary_write_d_text');
                if (editor) return editor.getContent();
                const iframe = document.getElementById('diary_write_d_text_ifr');
                if (iframe && iframe.contentDocument) return iframe.contentDocument.body.innerHTML;
                const textarea = document.getElementById('diary_write_d_text');
                return textarea ? textarea.value : '';
            }''')
            if image_url not in inserted_html:
                print("  Error: image URL was not inserted into the editor. Aborting before publish.")
                print(f"  Expected image URL: {image_url}")
                safe_screenshot(page, 'debug_content_missing_image.png')
                return None
            print("  Content verification: image URL is present")

            # ============================================
            # Step 4: 公開
            # ============================================
            print("Step 4: Publishing...")
            time.sleep(2)

            try:
                publish_btn = page.locator('#diary_write_public_submit')
                publish_btn.wait_for(state='visible', timeout=5000)
                publish_btn.click()
                print("  Publish button clicked")
                time.sleep(3)

                # 確認ダイアログの「公開する」をクリック（プロ活広告の確認）
                try:
                    confirm_btns = page.locator('a:visible:has-text("公開する"), button:visible:has-text("公開する")').all()
                    for btn in confirm_btns:
                        btn_id = btn.get_attribute('id') or ''
                        if btn_id != 'diary_write_public_submit':
                            btn.click()
                            print("  Confirmation dialog: clicked '公開する'")
                            break
                except Exception:
                    pass

                time.sleep(5)
                published = True
            except Exception as e:
                print(f"  Publish failed: {e}")
                published = False
                safe_screenshot(page, 'debug_publish_error.png')

            # ============================================
            # Step 5: 結果確認
            # ============================================
            final_url = page.url
            print(f"  Final URL: {final_url}")
            safe_screenshot(page, 'debug_final.png')

            # 公開完了ページのテキストで判定
            page_text = page.evaluate('() => document.body.innerText.substring(0, 500)')
            if '公開しました' in page_text:
                print("  Post successful!")
                article_url = final_url
            elif published and 'write' not in final_url:
                print("  Post appears successful")
                article_url = final_url
            elif published:
                print("  Post submitted, but result is unclear and still on write page")
                article_url = None
            else:
                print("  Post may have failed")
                article_url = None

            # Cookie保存
            cookies = context.cookies()
            with open(cookie_file, 'w') as f:
                json.dump(cookies, f)
            print("  Cookies saved")

            return article_url

        except Exception as e:
            print(f"Playwright error: {e}")
            try:
                safe_screenshot(page, 'debug_error.png')
            except Exception:
                pass
            return None

        finally:
            browser.close()


# ============================================================
# メイン
# ============================================================

def main():
    print("=== Rakuten Blog Auto Poster (GitHub Actions) ===\n")

    if not all([RAKUTEN_USER_ID, RAKUTEN_PASSWORD, RAKUTEN_BLOG_ID, GDRIVE_FOLDER_ID]):
        print("Error: Missing required environment variables")
        print("Required: RAKUTEN_USER_ID, RAKUTEN_PASSWORD, RAKUTEN_BLOG_ID, GDRIVE_FOLDER_ID")
        return 1

    # Load log
    log_data = load_uploaded_log()

    # ============================================
    # Step 1: Drive素材をランダム選択 → 楽天写真館へ新規アップロード
    # ============================================
    from playwright.sync_api import sync_playwright

    print("Step 1: Downloading Drive images and selecting a random unused file...")
    media_files = download_media()
    if not media_files:
        print("No images found in Google Drive folder!")
        return 1

    selected_media, available_media = select_media(media_files, log_data)
    if not selected_media:
        print("No selectable images found!")
        return 1

    print(f"Selected Drive image: {selected_media['source_key']}")
    print(f"Available: {len(available_media)} / Total: {len(media_files)}")

    try:
        prepared_image = prepare_image_for_rakuten(selected_media["path"])
    except Exception as e:
        print(f"Image preparation failed: {e}")
        return 1

    print("\nStep 2: Uploading selected image to Rakuten image library...")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            viewport={'width': 1280, 'height': 900},
        )
        cookie_file = 'rakuten_cookies.json'
        if os.path.exists(cookie_file):
            with open(cookie_file, 'r') as f:
                ctx.add_cookies(json.load(f))

        tmp_page = ctx.new_page()
        image_url = upload_image_to_rakuten(tmp_page, prepared_image)

        # Cookie保存
        cookies = ctx.cookies()
        with open(cookie_file, 'w') as f:
            json.dump(cookies, f)

        browser.close()

    if not image_url:
        print("Rakuten image upload failed; aborting before blog publish.")
        return 1

    print(f"Selected image: {image_url[:60]}...")

    # ============================================
    # Step 3: タグ・記事生成
    # ============================================
    tags = generate_tags(selected_media["source_key"])

    # トレンドタグ
    try:
        from trending import get_trending_tags
        trend_tags = get_trending_tags(max_tags=5)
        if trend_tags:
            seen = {t.lower() for t in tags}
            for t in trend_tags:
                if t.lower() not in seen:
                    tags.append(t)
                    seen.add(t.lower())
    except Exception as e:
        print(f"Trend tags skipped: {e}")

    # 記事HTML生成（画像URL埋め込み済み）
    title, content_html = build_blog_html(image_url, tags, selected_media["source_key"])
    print(f"Title: {title}")
    print(f"Content length: {len(content_html)} chars")

    # ============================================
    # Step 4: 投稿
    # ============================================
    article_url = post_to_rakuten_blog(image_url, title, content_html)

    if not article_url:
        print("Post may have failed!")
        return 1

    # Record
    log_data["files"].append({
        'file': os.path.basename(image_url),
        'source_key': selected_media["source_key"],
        'source_name': selected_media["source_name"],
        'image_url': image_url,
        'article_url': article_url,
        'title': title,
        'uploaded_at': time.strftime('%Y-%m-%d %H:%M:%S'),
    })
    save_uploaded_log(log_data)

    remaining = len(available_media) - 1
    print(f"\nDone! Remaining images: {remaining}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
