import os
import time
import scratchattach as scratch3
from datetime import datetime, timedelta, timezone

# --- 🛠️ 設定項目 🛠️ ---
READ_PROJECT_ID = "1304990524"
JST = timezone(timedelta(hours=+9), 'JST')
IGNORE_USERS = ["Unknown User"]

def get_github_pages_url():
    """GitHub Actionsの環境変数からPagesのURLを自動生成する"""
    repo = os.getenv("GITHUB_REPOSITORY") # "username/repo" の形式で取得できる
    if repo:
        user, repo_name = repo.split("/")
        return f"https://{user}.github.io/{repo_name}/"
    return "URL could not be generated."

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
        pages_url = get_github_pages_url()
        
        print(f"🔄 集計開始: {mode}")
        print(f"🌐 公開先URL: {pages_url}")
        
        project = scratch3.get_project(READ_PROJECT_ID)
        user_stats = {}
        counted_ids = set()

        # 集計処理 (最大5000件程度をスキャン)
        for offset in range(0, 5000, 40): 
            try:
                comments = project.comments(limit=40, offset=offset)
            except Exception as e:
                print(f"⚠ 取得失敗: {e}"); time.sleep(5); continue

            if not comments: break
            
            stop_signal = False
            for c in comments:
                if c.id in counted_ids: continue
                dt = parse_scratch_date(c.datetime_created)
                
                if dt > end_time_utc: continue
                if dt < start_time_utc:
                    stop_signal = True; break
                
                u = get_author_name(c)
                if u not in IGNORE_USERS:
                    if u not in user_stats: user_stats[u] = {"p": 0, "r": 0}
                    user_stats[u]["p"] += 1
                    counted_ids.add(c.id)
                
                if c.reply_count > 0:
                    try:
                        replies = c.replies(limit=40)
                        for r in replies:
                            if r.id in counted_ids: continue
                            dt_r = parse_scratch_date(r.datetime_created)
                            if start_time_utc <= dt_r <= end_time_utc:
                                ru = get_author_name(r)
                                if ru not in IGNORE_USERS:
                                    if ru not in user_stats: user_stats[ru] = {"p": 0, "r": 0}
                                    user_stats[ru]["r"] += 1
                                    counted_ids.add(r.id)
                    except: pass
            
            if stop_signal: break
            time.sleep(0.1)

        sorted_users = sorted(user_stats.items(), key=lambda x: (x[1]["p"] + x[1]["r"]), reverse=True)

        # --- HTML作成 ---
        display_date = (now_jst - timedelta(days=1) if mode == "yesterday" else now_jst).strftime('%m/%d')
        title_label = "昨日" if mode == "yesterday" else "今日"
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Ranking: {display_date}</title>
            <style>
                body {{ font-family: sans-serif; background: #f0f2f5; padding: 15px; }}
                .container {{ background: white; padding: 20px; border-radius: 10px; max-width: 600px; margin: auto; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                h1 {{ color: #4d97ff; text-align: center; }}
                .info {{ text-align: center; color: #777; font-size: 0.8em; margin-bottom: 20px; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ padding: 10px 5px; border-bottom: 1px solid #eee; text-align: center; }}
                th {{ background: #4d97ff; color: white; }}
                .user {{ text-align: left; font-weight: bold; }}
                .rank-1 {{ background: #fff9c4; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🏆 {title_label}のコメントランキング ({display_date})</h1>
                <p class="info">最終更新: {now_jst.strftime('%H:%M:%S')}<br>公開URL: {pages_url}</p>
                <table>
                    <thead><tr><th>順位</th><th>ユーザー</th><th>合計</th><th>コメ</th><th>返信</th></tr></thead>
                    <tbody>
        """
        for i, (user, stat) in enumerate(sorted_users):
            total = stat["p"] + stat["r"]
            row_class = 'class="rank-1"' if i == 0 else ""
            html_content += f"""
                        <tr {row_class}>
                            <td>{i+1}</td>
                            <td class="user">@{user}</td>
                            <td>{total}</td>
                            <td>{stat['p']}</td>
                            <td>{stat['r']}</td>
                        </tr>"""
        html_content += "</tbody></table></div></body></html>"

        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print("✅ HTML更新完了")

    except Exception as e:
        print(f"❌ エラー: {e}")

if __name__ == "__main__":
    run_ranking()
