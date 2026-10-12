import sys
import httpx

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

if __name__ == "__main__":
    client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=60.0)

    course_id = "88aa5b79-3051-4ce6-b4e2-edb568146e52"
    questions = [
        ("PDF", "What is Newton's second law of motion and what is its mathematical formula?"),
        ("PPTX", "According to the presentation slides, what are the three main components of an electric motor?"),
        ("MP4", "According to Bernoulli's principle in the fluid mechanics lecture video, what happens to pressure when velocity increases?"),
        ("YouTube", "How many neurons make up the input layer of the neural network for a 28 by 28 pixel image?")
    ]

    print("=" * 80)
    print(f"QUERYING TUTOR SERVICE FOR COURSE: {course_id}")
    print("=" * 80)

    for mod, q in questions:
        res = client.post("/api/tutor/chat", json={"course_id": course_id, "message": q})
        print("\n" + "-" * 70)
        print(f"[{mod}] Question: {q}")
        print(f"Status Code: {res.status_code}")
        data = res.json()
        print("Grounded:", data.get("grounded"))
        print("Answer:", data.get("answer"))
        sources = data.get("sources", [])
        print(f"Total Sources Returned: {len(sources)}")
        for idx, s in enumerate(sources, 1):
            loc = (
                f"page={s.get('page')}" if s.get('page') is not None
                else f"slide={s.get('slide')}" if s.get('slide') is not None
                else f"ts={s.get('start_seconds')}-{s.get('end_seconds')}" if s.get('start_seconds') is not None
                else "none"
            )
            print(f"  [{idx}] file={s.get('file_name')} | modality={s.get('modality')} | {loc} | sid={s.get('source_id')}")
            print(f"      excerpt={repr(s.get('excerpt', '')[:100])}")

