# -*- coding: utf-8 -*-
"""
Google Trendsからニッチ関連のトレンドタグを取得する共通モジュール
"""
import random

SEED_KEYWORDS = [
    'muscle girl',
    'female bodybuilder',
    'fitness motivation',
    'gym workout',
    'strong women',
]

RELEVANCE_KEYWORDS = {
    'muscle', 'fitness', 'gym', 'workout', 'bodybuilding', 'strong',
    'fit', 'training', 'exercise', 'physique', 'flex', 'gains',
    'bicep', 'abs', 'squat', 'deadlift', 'bench', 'crossfit',
    'yoga', 'pilates', 'cardio', 'protein', 'bulk', 'shred',
    'ripped', 'lean', 'athletic', 'fbb', 'ifbb', 'npc',
    'bodybuilder', 'powerlifting', 'weightlifting', 'calisthenics',
    '筋トレ', '筋肉', 'フィットネス', 'ジム', 'トレーニング',
}


def get_trending_tags(max_tags=5):
    try:
        from pytrends.request import TrendReq
    except ImportError:
        print("pytrends not installed, skipping trend tags")
        return []

    trending_tags = []
    try:
        pytrends = TrendReq(hl='en-US', tz=360, timeout=(10, 25))
        seeds = random.sample(SEED_KEYWORDS, min(2, len(SEED_KEYWORDS)))
        print(f"Fetching trends for: {seeds}")
        pytrends.build_payload(seeds, cat=0, timeframe='now 7-d', geo='', gprop='')
        related = pytrends.related_queries()
        for keyword in seeds:
            data = related.get(keyword, {})
            rising = data.get('rising')
            if rising is not None and not rising.empty:
                for _, row in rising.head(10).iterrows():
                    query = row['query'].strip().lower()
                    if _is_relevant(query):
                        trending_tags.append(query.replace(' ', ''))
            top = data.get('top')
            if top is not None and not top.empty:
                for _, row in top.head(5).iterrows():
                    query = row['query'].strip().lower()
                    if _is_relevant(query):
                        trending_tags.append(query.replace(' ', ''))

        seen = set()
        unique = []
        for t in trending_tags:
            if t.lower() not in seen:
                seen.add(t.lower())
                unique.append(t)
        random.shuffle(unique)
        result = unique[:max_tags]
        if result:
            print(f"Trending tags found: {result}")
        else:
            print("No relevant trending tags found")
        return result
    except Exception as e:
        print(f"Trend fetch failed (non-fatal): {e}")
        return []


def _is_relevant(query):
    query_lower = query.lower()
    return any(kw in query_lower for kw in RELEVANCE_KEYWORDS)
