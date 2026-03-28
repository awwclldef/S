import requests

def fetch_comments(studio_id, limit=40, offset=0):
    url = f"https://api.scratch.mit.edu/studios/{studio_id}/comments"
    
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    params = {
        "limit": limit,
        "offset": offset
    }

    res = requests.get(url, headers=headers, params=params)

    if res.status_code != 200:
        print("エラー:", res.status_code)
        return []

    return res.json()


def fetch_all_comments(studio_id):
    comments = []
    offset = 0

    while True:
        data = fetch_comments(studio_id, offset=offset)
        
        if not data:
            break
        
        comments.extend(data)
        offset += 40

    return comments


def main():
    studio_id = input("スタジオID: ")
    
    comments = fetch_all_comments(studio_id)

    # 上から順（古い順）にする
    comments.reverse()

    for i, c in enumerate(comments, 1):
        print(f"{i}. {c['author']['username']}: {c['content']}")


if __name__ == "__main__":
    main()
