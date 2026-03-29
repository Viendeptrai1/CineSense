# CineSen Retrieval Judge Rubric v1

You are evaluating whether a retrieved movie is relevant to an English natural-language movie query.

## Inputs
- `query`: user search text
- `query_stratum`: one of `keyword`, `vibe`, `detailed`
- `candidate_title`
- `candidate_genres`
- `candidate_overview`
- `candidate_review_summary`

## Scoring Rules
- Focus on **semantic relevance** to the query, not popularity.
- Use the review summary as the primary evidence when it is informative; use overview and genres as supporting evidence.
- Do not reward a result just because it matches one genre token if the rest of the description is off.
- If the query is vibe-heavy, check tone, emotional signal, and aspect cues such as `visuals`, `acting`, `script`, `music`, `pacing`, or `direction`.
- If the query is detailed, prefer results that satisfy multiple constraints together.

## Output Schema
Return a single JSON object with exactly these keys:

```json
{
  "binary_relevant": true,
  "relevance_score": 4,
  "constraint_match_score": 4,
  "review_signal_score": 5,
  "reasoning": "Short explanation grounded in candidate evidence.",
  "matched_clues": ["space survival", "strong visuals"]
}
```

## Field Definitions
- `binary_relevant`: `true` if this candidate is a sensible recommendation for the query.
- `relevance_score`: integer `0..5`
- `constraint_match_score`: integer `0..5`
- `review_signal_score`: integer `0..5`
- `reasoning`: 1-3 sentences, concrete and evidence-based.
- `matched_clues`: short list of phrases from the query or candidate evidence that explain the score.
