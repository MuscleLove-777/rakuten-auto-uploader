# -*- coding: utf-8 -*-
"""
楽天ブログ自動投稿（GitHub Actions用）
Google Driveからダウンロード → ランダム1ファイル → Playwrightで楽天ブログに投稿
※ 楽天ブログにはAPIがないため、ブラウザ自動操作で投稿する
"""
import sys, json, os, random, time, re

import requests
import gdown

# ============================================================
# 設定
# ============================================================

GDRIVE_FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID", "")
RAKUTEN_USER_ID = os.environ.get("RAKUTEN_USER_ID", "")
RAKUTEN_PASSWORD = os.environ.get("RAKUTEN_PASSWORD", "")
RAKUTEN_BLOG_ID = os.environ.get("RAKUTEN_BLOG_ID", "")  # plaza.rakuten.co.jp/{BLOG_ID}/

PATREON_LINK = "https://www.patreon.com/cw/MuscleLove"
IMAGE_EXTENSIONS = {'.jpg', '.jpeg'}  # 楽天写真館はJPEGのみ
MAX_FILE_SIZE = 20 * 1024 * 1024  # 楽天写真館上限: 20MB
UPLOADED_LOG = "uploaded.json"

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


# ============================================================
# Google Driveダウンロード
# ============================================================

def download_media():
    dl_dir = "media"
    os.makedirs(dl_dir, exist_ok=True)
    url = f"https://drive.google.com/drive/folders/{GDRIVE_FOLDER_ID}"
    print(f"Downloading from Google Drive: {url}")
    try:
        gdown.download_folder(url, output=dl_dir, quiet=False, remaining_ok=True)
    except Exception as e:
        print(f"Download error: {e}")

    files = []
    for root, dirs, filenames in os.walk(dl_dir):
        for fname in filenames:
            fpath = os.path.join(root, fname)
            ext = os.path.splitext(fname)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                size = os.path.getsize(fpath)
                if size <= MAX_FILE_SIZE:
                    files.append(fpath)
                else:
                    print(f"Skip (>20MB): {fname} ({size / 1024 / 1024:.1f}MB)")
    return files


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


def build_blog_content(tags, file_path):
    """記事のタイトルと本文を生成"""
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

    # 楽天ブログはリッチエディタなので、改行は\nでOK
    content = f"""{opening}

{intro}

（画像は上に挿入済み）

{body}

{closing}

━━━━━━━━━━━━━━━━━━
🔥 もっと見たい？ Patreonで限定コンテンツ公開中！
👉 {PATREON_LINK}
ここでしか見れない筋肉美をお届け中💪
━━━━━━━━━━━━━━━━━━

{hashtag_text}"""

    return title, content


# ============================================================
# Playwright: 楽天ブログに投稿
# ============================================================

def post_to_rakuten_blog(image_path, title, content):
    """Playwrightで楽天ブログにログイン → 画像アップ → 記事投稿"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 800},
        )

        # Cookie保存用
        cookie_file = 'rakuten_cookies.json'
        if os.path.exists(cookie_file):
            with open(cookie_file, 'r') as f:
                cookies = json.load(f)
            context.add_cookies(cookies)
            print("Loaded saved cookies")

        page = context.new_page()

        try:
            # ============================================
            # Step 1: ログイン
            # ============================================
            print("Step 1: Logging in to Rakuten...")
            page.goto('https://plaza.rakuten.co.jp/diarywrite/', wait_until='domcontentloaded', timeout=30000)
            time.sleep(3)

            # ログインページにリダイレクトされた場合
            if 'grp' in page.url and 'LOGIN' in page.url.upper() or 'id.rakuten' in page.url:
                print("Login page detected, entering credentials...")

                # ユーザーID入力
                user_field = page.locator('input[name="u"], input[id="loginInner_u"]').first
                user_field.fill(RAKUTEN_USER_ID)
                time.sleep(1)

                # パスワード入力
                pass_field = page.locator('input[name="p"], input[id="loginInner_p"]').first
                pass_field.fill(RAKUTEN_PASSWORD)
                time.sleep(1)

                # ログインボタン
                login_btn = page.locator('input[type="submit"], button[type="submit"]').first
                login_btn.click()
                time.sleep(5)

                # ログイン後のページを確認
                print(f"After login URL: {page.url}")

                if 'error' in page.url.lower() or 'login' in page.url.lower():
                    print("Login may have failed. Trying to continue anyway...")
            else:
                print("Already logged in (cookies worked)")

            # ============================================
            # Step 2: 日記作成ページに移動
            # ============================================
            print("Step 2: Navigating to diary write page...")
            page.goto(f'https://plaza.rakuten.co.jp/{RAKUTEN_BLOG_ID}/diarywrite/',
                      wait_until='domcontentloaded', timeout=30000)
            time.sleep(3)

            current_url = page.url
            print(f"Current URL: {current_url}")

            # ============================================
            # Step 3: タイトル入力
            # ============================================
            print(f"Step 3: Setting title: {title}")

            # タイトルフィールドを探す
            title_selectors = [
                'input[name="title"]',
                'input#title',
                'input[name="diary_title"]',
                'input.titleInput',
                'input[placeholder*="タイトル"]',
            ]

            title_filled = False
            for selector in title_selectors:
                try:
                    el = page.locator(selector).first
                    if el.is_visible(timeout=3000):
                        el.fill(title)
                        title_filled = True
                        print(f"  Title filled via: {selector}")
                        break
                except Exception:
                    continue

            if not title_filled:
                print("  Warning: Could not find title field, trying fallback...")
                # フォールバック: 最初のtext inputを試す
                try:
                    page.locator('input[type="text"]').first.fill(title)
                    title_filled = True
                    print("  Title filled via fallback (first text input)")
                except Exception as e:
                    print(f"  Title fill failed: {e}")

            # ============================================
            # Step 4: 画像アップロード
            # ============================================
            print(f"Step 4: Uploading image: {os.path.basename(image_path)}")

            # 画像挿入ボタンを探してクリック
            image_btn_selectors = [
                'a[title*="画像"]',
                'button[title*="画像"]',
                'a:has-text("画像")',
                'img[alt*="画像"]',
                '.imageBtn',
                'a[href*="image"]',
            ]

            image_btn_clicked = False
            for selector in image_btn_selectors:
                try:
                    el = page.locator(selector).first
                    if el.is_visible(timeout=3000):
                        el.click()
                        image_btn_clicked = True
                        print(f"  Image button clicked: {selector}")
                        time.sleep(3)
                        break
                except Exception:
                    continue

            if image_btn_clicked:
                # ファイル入力を探してアップロード
                try:
                    file_input = page.locator('input[type="file"]').first
                    file_input.set_input_files(image_path)
                    print("  Image file selected")
                    time.sleep(5)

                    # アップロード/挿入ボタンを探してクリック
                    upload_selectors = [
                        'button:has-text("挿入")',
                        'button:has-text("アップロード")',
                        'input[value*="挿入"]',
                        'input[value*="アップロード"]',
                        'button:has-text("OK")',
                        'a:has-text("挿入")',
                    ]
                    for sel in upload_selectors:
                        try:
                            btn = page.locator(sel).first
                            if btn.is_visible(timeout=3000):
                                btn.click()
                                print(f"  Upload/Insert clicked: {sel}")
                                time.sleep(3)
                                break
                        except Exception:
                            continue
                except Exception as e:
                    print(f"  Image upload via button failed: {e}")
            else:
                # フォールバック: 直接file inputを探す
                print("  Image button not found, trying direct file input...")
                try:
                    file_input = page.locator('input[type="file"]').first
                    file_input.set_input_files(image_path)
                    print("  Image file selected (direct)")
                    time.sleep(5)
                except Exception as e:
                    print(f"  Direct file input failed: {e}")
                    print("  Continuing without image...")

            # ============================================
            # Step 5: 本文入力
            # ============================================
            print("Step 5: Entering content...")

            # リッチエディタ（iframe内）またはtextareaに本文を入力
            content_filled = False

            # パターン1: iframe内のリッチエディタ
            try:
                frames = page.frames
                for frame in frames:
                    try:
                        body_el = frame.locator('body[contenteditable="true"], body.mceContentBody').first
                        if body_el.is_visible(timeout=2000):
                            # 既存コンテンツの後に追加（画像が挿入されてる可能性）
                            existing = body_el.inner_html()
                            body_el.evaluate(f'(el) => {{ el.innerHTML = el.innerHTML + "<br><br>" + {json.dumps(content.replace(chr(10), "<br>"))}; }}')
                            content_filled = True
                            print("  Content filled via iframe rich editor")
                            break
                    except Exception:
                        continue
            except Exception:
                pass

            # パターン2: textarea
            if not content_filled:
                textarea_selectors = [
                    'textarea[name="diary_body"]',
                    'textarea[name="body"]',
                    'textarea#body',
                    'textarea.bodyTextarea',
                    'textarea',
                ]
                for selector in textarea_selectors:
                    try:
                        el = page.locator(selector).first
                        if el.is_visible(timeout=3000):
                            el.fill(content)
                            content_filled = True
                            print(f"  Content filled via: {selector}")
                            break
                    except Exception:
                        continue

            if not content_filled:
                print("  Warning: Could not fill content body")

            # ============================================
            # Step 6: 投稿（公開）
            # ============================================
            print("Step 6: Publishing...")
            time.sleep(2)

            publish_selectors = [
                'input[value*="公開"]',
                'button:has-text("公開")',
                'input[value*="投稿"]',
                'button:has-text("投稿")',
                'input[name="publish"]',
                'input[type="submit"][value*="日記"]',
                'button[type="submit"]',
            ]

            published = False
            for selector in publish_selectors:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible(timeout=3000):
                        btn.click()
                        published = True
                        print(f"  Publish clicked: {selector}")
                        time.sleep(5)
                        break
                except Exception:
                    continue

            if not published:
                print("  Warning: Could not find publish button")
                # スクリーンショットを保存してデバッグ用
                page.screenshot(path='debug_publish.png')
                print("  Debug screenshot saved: debug_publish.png")

            # ============================================
            # Step 7: 結果確認
            # ============================================
            final_url = page.url
            print(f"Final URL: {final_url}")

            # 投稿成功の判定
            if 'diary' in final_url and 'write' not in final_url:
                print("Post appears successful!")
                article_url = final_url
            elif published:
                print("Post submitted (checking result...)")
                article_url = final_url
            else:
                print("Post may have failed")
                article_url = None

            # Cookie保存（次回ログイン省略用）
            cookies = context.cookies()
            with open(cookie_file, 'w') as f:
                json.dump(cookies, f)
            print("Cookies saved for next run")

            return article_url

        except Exception as e:
            print(f"Playwright error: {e}")
            try:
                page.screenshot(path='debug_error.png')
                print("Debug screenshot saved: debug_error.png")
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

    # Download media from Google Drive
    media_files = download_media()
    if not media_files:
        print("No JPEG files found! (Rakuten Blog only supports JPEG)")
        return 0

    # Filter out already uploaded
    if os.environ.get("UPLOAD_ALL", "").lower() in ("1", "true", "yes"):
        available = media_files
        print(f"\nUPLOAD_ALL enabled: all {len(available)} files are candidates")
    else:
        uploaded_names = [entry['file'] if isinstance(entry, dict) else entry
                          for entry in log_data.get("files", [])]
        available = [f for f in media_files if os.path.basename(f) not in uploaded_names]
        if not available:
            print("All files already uploaded!")
            return 0
        print(f"\nAvailable: {len(available)} / Total: {len(media_files)}")

    # Select random file
    selected = random.choice(available)
    fname = os.path.basename(selected)
    print(f"Selected: {fname}")

    # Generate tags
    tags = generate_tags(selected)

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

    # 記事生成
    title, content = build_blog_content(tags, selected)
    print(f"Title: {title}")
    print(f"Content preview: {content[:100]}...")

    # Playwrightで投稿
    article_url = post_to_rakuten_blog(selected, title, content)

    if not article_url:
        print("Post may have failed!")
        return 1

    # Record uploaded file
    log_data["files"].append({
        'file': fname,
        'article_url': article_url,
        'title': title,
        'uploaded_at': time.strftime('%Y-%m-%d %H:%M:%S'),
    })
    save_uploaded_log(log_data)

    remaining = len(available) - 1
    print(f"\nDone! Remaining: {remaining}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
