import os
import time
import scratchattach as scratch3
from datetime import datetime, timedelta, timezone

# --- 設定項目 ---
READ_PROJECT_ID = "1304990524"
WRITE_PROJECT_ID = "1293676241"

JST = timezone(timedelta(hours=+9), 'JST')
IGNORE_USERS = ["Unknown User"]

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
        
        project = scratch3.get_project(READ_PROJECT_ID)
        project.update() 
        user_stats = {}
        counted_ids = set()

        for offset in range(0, 20000, 40): 
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
                        for r_offset in range(0, c.reply_count + 40, 40):
                            replies = c.replies(limit=40, offset=r_offset)
                            if not replies: break
                            for r in replies:
                                if r.id in counted_ids: continue
                                dt_r = parse_scratch_date(r.datetime_created)
                                if start_time_utc <= dt_r <= end_time_utc:
                                    ru = get_author_name(r)
                                    if ru not in IGNORE_USERS:
                                        if ru not in user_stats: user_stats[ru] = {"p": 0, "r": 0}
                                        user_stats[ru]["r"] += 1
                                        counted_ids.add(r.id)
                            if len(replies) < 40: break
                    except: pass
            
            if stop_signal: break
            time.sleep(0.1)

        sorted_users = sorted(user_stats.items(), key=lambda x: (x[1]["p"] + x[1]["r"]), reverse=True)

        # --- 🏆 Scratch用テキスト (※AM 4:00〜の文言を削除) ---
        display_date = (now_jst - timedelta(days=1) if mode == "yesterday" else now_jst).strftime('%m/%d')
        title_label = "昨日の最終" if mode == "yesterday" else "本日の"
        
        scratch_text = f"🏆 {title_label}活動ランキング ({display_date})\n"
        scratch_text += f"最終更新: {now_jst.strftime('%H:%M:%S')}\n"
        scratch_text += "--------------------------------\n"
        
        if not sorted_users:
            scratch_text += "対象期間の活動はありません。\n"
        else:
            for i, (user, stat) in enumerate(sorted_users[:15]):
                total = stat["p"] + stat["r"]
                scratch_text += f"{i+1}位: @{user} {total}回 (コメ:{stat['p']} 返信:{stat['r']})\n"

        # --- 🚀 Scratchへ反映 ---
        if USERNAME and PASSWORD:
            try:
                session = scratch3.login(USERNAME, PASSWORD)
                project_to_edit = session.connect_project(WRITE_PROJECT_ID)
                project_to_edit.set_notes(scratch_text)
                print("✅ Scratch更新完了")
            except Exception as e:
                print(f"❌ Scratch更新エラー: {e}")

        # --- 🌐 HTML作成 ---
        html_content = f"""
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Detailed Ranking</title>
            <style>
                body {{ font-family: sans-serif; background: #f4f7f6; padding: 10px; }}
                .container {{ background: white; padding: 20px; border-radius: 15px; max-width: 800px; margin: auto; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
                h1 {{ color: #00897b; text-align: center; border-bottom: 3px solid #00897b; padding-bottom: 10px; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
                th, td {{ padding: 12px 8px; border-bottom: 1px solid #eee; text-align: center; }}
                th {{ background: #00897b; color: white; }}
                .user-name {{ text-align: left; font-weight: bold; }}
                .total-num {{ font-weight: bold; color: #00897b; font-size: 1.1em; }}
                .sub-num {{ color: #666; font-size: 0.85em; }}
                .rank-1 {{ background: #e0f2f1; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🏆 {title_label}ランキング ({display_date})</h1>
                <p style="text-align:center; color:#888;">更新: {now_jst.strftime('%H:%M:%S')}</p>
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
                            <td class="user-name">@{user}</td>
                            <td class="total-num">{total}</td>
                            <td class="sub-num">{stat['p']}</td>
                            <td class="sub-num">{stat['r']}</td>
                        </tr>"""
        html_content += "</tbody></table></div></body></html>"

        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print("✅ HTML更新完了")

    except Exception as e:
        print(f"❌ エラー: {e}"); raise e 

if __name__ == "__main__":
    run_ranking()
