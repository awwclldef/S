import os
import time
import scratchattach as scratch3
from datetime import datetime, timedelta, timezone

# --- 🛠️ 設定項目 🛠️ ---
READ_PROJECT_ID = "1304990524"  # コメントを読み取るプロジェクトID
WRITE_PROJECT_ID = "1293676241" # ランキングを書き込むプロジェクトID

# GitHub PagesのURL設定 (★ここをあなたの環境に合わせて書き換えてください★)
GITHUB_USERNAME = "YOUR_GITHUB_USERNAME"  # 例: "scratch_user"
GITHUB_REPO_NAME = "YOUR_REPO_NAME"      # 例: "comment-ranking"

JST = timezone(timedelta(hours=+9), 'JST')
IGNORE_USERS = ["Unknown User"]

# GitHub ActionsのSecretsから読み込む (ローカル実行時は環境変数を設定してください)
USERNAME = os.getenv("SCRATCH_USERNAME")
PASSWORD = os.getenv("SCRATCH_PASSWORD")

def get_author_name(comment):
    try:
        author = comment.author() if hasattr(comment, 'author') and callable(comment.author) else comment.author
        return str(author)
    except Exception:
        return "Unknown User"

def parse_scratch_date(date_str):
    return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)

def get_time_range():
    now_jst = datetime.now(JST)
    # AM 4:00までは「昨日」の扱いとする
    if now_jst.hour < 4:
        target_date = now_jst - timedelta(days=1)
        mode = "yesterday"
    else:
        target_date = now_jst
        mode = "today"
        
    start_jst = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = start_jst.astimezone(timezone.utc)
    end_jst = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    end_utc = end_jst.astimezone(timezone.utc)
    
    return start_utc, end_utc, mode

def run_ranking():
    try:
        now_jst = datetime.now(JST)
        start_time_utc, end_time_utc, mode = get_time_range()
        
        print(f"🔄 集計開始: {mode} (期間: {start_time_utc} ～ {end_time_utc})")
        
        project = scratch3.get_project(READ_PROJECT_ID)
        project.update() 
        user_stats = {}
        counted_ids = set()

        # コメント取得ループ (最大10000件)
        for offset in range(0, 10000, 40): 
            try:
                comments = project.comments(limit=40, offset=offset)
            except Exception as e:
                print(f"⚠ 取得失敗: {e}"); time.sleep(5); continue

            if not comments: break
            
            stop_signal = False
            for c in comments:
                if c.id in counted_ids: continue
                dt = parse_scratch_date(c.datetime_created)
                
                # 未来のコメント（通常ありえない）はスキップ
                if dt > end_time_utc: continue
                
                # 期間外（過去）のコメントに到達したらループ終了
                if dt < start_time_utc:
                    stop_signal = True; break
                
                # 親コメントの集計
                u = get_author_name(c)
                if u not in IGNORE_USERS:
                    if u not in user_stats: user_stats[u] = {"p": 0, "r": 0}
                    user_stats[u]["p"] += 1
                    counted_ids.add(c.id)
                
                # 返信（リプライ）の処理
                if c.reply_count > 0:
                    try:
                        for r_offset in range(0, c.reply_count + 40, 40):
                            replies = c.replies(limit=40, offset=r_offset)
                            if not replies: break
                            for r in replies:
                                if r.id in counted_ids: continue
                                dt_r = parse_scratch_date(r.datetime_created)
                                # 返信も期間内かチェック
                                if start_time_utc <= dt_r <= end_time_utc:
                                    ru = get_author_name(r)
                                    if ru not in IGNORE_USERS:
                                        if ru not in user_stats: user_stats[ru] = {"p": 0, "r": 0}
                                        user_stats[ru]["r"] += 1
                                        counted_ids.add(r.id)
                            if len(replies) < 40: break # 全返信取得完了
                    except: pass # 返信取得エラーは個別に無視
            
            if stop_signal: break # 期間外コメントに到達
            time.sleep(0.1) # 負荷軽減

        # 合計活動数でソート (上位15名)
        sorted_users = sorted(user_stats.items(), key=lambda x: (x[1]["p"] + x[1]["r"]), reverse=True)

        # --- 🏆 Scratch用テキスト作成 🏆 ---
        display_date = (now_jst - timedelta(days=1) if mode == "yesterday" else now_jst).strftime('%m/%d')
        title_label = "昨日の最終" if mode == "yesterday" else "本日の"
        
        scratch_text = f"🏆 {title_label}活動ランキング ({display_date})\n"
        scratch_text += f"最終更新: {now_jst.strftime('%H:%M:%S')}\n"
        scratch_text += "--------------------------------\n"
        
        if not sorted_users:
            scratch_text += "対象期間の活動はありません。\n"
        else:
            # 上位15名を表示
            for i, (user, stat) in enumerate(sorted_users[:15]):
                total = stat["p"] + stat["r"]
                scratch_text += f"{i+1}位: @{user} {total}回 (コメ:{stat['p']} 返信:{stat['r']})\n"

        # --- ★追加機能: 詳しいランキングサイトのURLを追記★ ---
        # ユーザー名とリポジトリ名が初期設定のままでないかチェック
        if GITHUB_USERNAME != "YOUR_GITHUB_USERNAME" and GITHUB_REPO_NAME != "YOUR_REPO_NAME":
            pages_url = f"https://{GITHUB_USERNAME}.github.io/{GITHUB_REPO_NAME}/"
            scratch_text += "--------------------------------\n"
            scratch_text += f"🌐 全員の詳しいランキングはこちら:\n"
            scratch_text += pages_url + "\n"
        else:
            print("⚠ GITHUB設定が初期のままのため、URL追記をスキップします。")

        # --- 🚀 Scratchへ反映 (メモとクレジット) 🚀 ---
        if USERNAME and PASSWORD:
            try:
                session = scratch3.login(USERNAME, PASSWORD)
                project_to_edit = session.connect_project(WRITE_PROJECT_ID)
                project_to_edit.set_notes(scratch_text) # 「メモとクレジット」に書き込み
                print("✅ Scratchプロジェクト更新完了")
            except Exception as e:
                print(f"❌ Scratch更新エラー (ログイン情報やプロジェクトIDを確認してください): {e}")
        else:
            print("⚠ SCRATCH_USERNAME または SCRATCH_PASSWORD が設定されていないため、Scratchへの反映をスキップします。")

        # --- 🌐 HTML作成 (GitHub Pages用) 🌐 ---
        html_content = f"""
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Detailed Ranking ({display_date})</title>
            <style>
                body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background: #f4f7f6; padding: 20px; color: #333; }}
                .container {{ background: white; padding: 20px; border-radius: 12px; max-width: 750px; margin: auto; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
                h1 {{ color: #4d97ff; text-align: center; border-bottom: 2px solid #4d97ff; padding-bottom: 10px; margin-bottom: 5px; }}
                .update-info {{ text-align: center; color: #888; font-size: 0.85em; margin-bottom: 20px; }}
                table {{ border-collapse: collapse; width: 100%; font-size: 0.95em; }}
                th, td {{ padding: 12px 8px; border-bottom: 1px solid #eee; text-align: center; }}
                th {{ background: #4d97ff; color: white; }}
                .user-name {{ text-align: left; font-weight: bold; }}
                .total-num {{ font-weight: bold; color: #4d97ff; font-size: 1.1em; }}
                .sub-num {{ color: #777; font-size: 0.8em; }}
                .rank-1 {{ background: #e3f2fd; }} /* 1位の行の色 */
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🏆 {title_label}コメント活動ランキング ({display_date})</h1>
                <p class="update-info">最終自動更新: {now_jst.strftime('%H:%M:%S')}</p>
                <table>
                    <thead><tr><th>順位</th><th>ユーザー</th><th>合計</th><th>コメ</th><th>返信</th></tr></thead>
                    <tbody>
        """
        # 全員のデータを表に追加
        for i, (user, stat) in enumerate(sorted_users):
            total = stat["p"] + stat["r"]
            row_class = 'class="rank-1"' if i == 0 else "" # 1位だけスタイル変更
            html_content += f"""
                        <tr {row_class}>
                            <td>{i+1}</td>
                            <td class="user-name">@{user}</td>
                            <td class="total-num">{total}</td>
                            <td class="sub-num">{stat['p']}</td>
                            <td class="sub-num">{stat['r']}</td>
                        </tr>"""
        html_content += "</tbody></table></div></body></html>"

        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print("✅ HTMLファイル (index.html) 更新完了")

    except Exception as e:
        print(f"❌ 致命的なエラー発生: {e}")
        raise e # GitHub Actionsにエラーを通知

if __name__ == "__main__":
    run_ranking()
