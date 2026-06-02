from __future__ import annotations

"""
LLM 심사 코멘트: prediction_result + explanation_result(SHAP) → 한국어 보고서 톤 코멘트.
"""

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.tables import ExplanationResult, LlmReviewResult, PredictionResult
from app.repositories import explanation_repository as expl_repo
from app.repositories import llm_review_repository as review_repo
from app.repositories import prediction_repository as pred_repo


class LlmNotConfiguredError(Exception):
    """OPENAI_API_KEY 미설정."""

    pass


class LlmGenerationError(Exception):
    """LLM API 호출 실패 또는 빈 응답."""

    pass


_SYSTEM_PROMPT = """\
당신은 국내 금융기관의 여신(대출) 심사 보고서를 작성하는 심사 보조 역할입니다.
출력은 반드시 한국어로만 작성합니다.
문체는 공식 심사 의견서에 맞게 간결·명확하게 하며, 과장·확정적 단정은 피하고 모델 결과를 전제로 서술합니다.
3~6문장 정도로 마무리합니다."""


def _format_shap_block(rows: list[ExplanationResult]) -> str:
    lines: list[str] = []
    for r in rows:
        sv = float(r.shap_value)
        if sv > 0:
            direction = "부실 확률 증가 기여"
        elif sv < 0:
            direction = "부실 확률 감소 기여"
        else:
            direction = "기여 중립"
        lines.append(
            f"{r.rank}. 변수 `{r.feature_name}` — SHAP {sv:+.6f} ({direction})",
        )
    return "\n".join(lines)


def _build_user_prompt(pred: PredictionResult, explanations: list[ExplanationResult]) -> str:
    rs = float(pred.risk_score)
    shap_block = _format_shap_block(explanations)
    return f"""다음은 대출 부실(연체) 예측 모델의 결과와 SHAP으로 요약한 주요 변수 기여입니다.

## 예측 요약
- 신청 ID: {pred.application_id}
- 부실 예측 확률 (risk_score): {rs:.6f}
- 리스크 등급 (risk_grade): {pred.risk_grade}
- 임계 기반 예측 부실 여부 (predicted_default_yn): {pred.predicted_default_yn}

## 주요 위험·완화 요인 (SHAP, 상위 변수)
{shap_block}

위 정보를 바탕으로 심사자가 참고할 수 있는 **심사 코멘트**를 작성하세요.
요구: 금융 심사 보고서 톤, 핵심만 간결히, 한국어만."""


def _call_llm(*, system: str, user: str, model: str, api_key: str, base_url: str | None) -> str:
    from openai import OpenAI

    kwargs: dict = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.25,
        )
    except Exception as exc:
        msg = f"LLM API 오류: {exc}"
        raise LlmGenerationError(msg) from exc

    choice = resp.choices[0].message.content
    if not choice or not str(choice).strip():
        msg = "LLM 응답이 비어 있습니다."
        raise LlmGenerationError(msg)
    return str(choice).strip()


def get_or_create_llm_review(session: Session, prediction_id: int) -> LlmReviewResult:
    """
    저장된 심사 코멘트가 있으면 반환하고, 없으면 LLM 생성 후 ``llm_review_result``에 저장합니다.
    """
    pred = pred_repo.get_prediction_by_id(session, prediction_id)
    if pred is None:
        msg = f"prediction_id={prediction_id} not found"
        raise LookupError(msg)

    cached = review_repo.get_by_prediction_id(session, prediction_id)
    if cached is not None:
        return cached

    explanations = expl_repo.list_by_prediction_id(session, prediction_id)
    if not explanations:
        msg = (
            "SHAP 설명이 없습니다. 먼저 POST /api/v1/explanations 로 설명을 생성하세요."
        )
        raise ValueError(msg)

    settings = get_settings()
    if not settings.openai_api_key:
        raise LlmNotConfiguredError(
            "OPENAI_API_KEY 가 설정되지 않았습니다. .env 에 키를 추가하세요.",
        )

    user_prompt = _build_user_prompt(pred, explanations)
    text = _call_llm(
        system=_SYSTEM_PROMPT,
        user=user_prompt,
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )

    row = LlmReviewResult(
        application_id=pred.application_id,
        prediction_id=int(pred.id),
        review_comment=text,
        llm_model=settings.llm_model,
    )
    session.add(row)
    session.flush()
    return row


def review_to_response_dict(row: LlmReviewResult, pred: PredictionResult) -> dict:
    """Pydantic 응답용 dict."""
    return {
        "prediction_id": int(pred.id),
        "application_id": pred.application_id,
        "risk_score": float(pred.risk_score),
        "risk_grade": pred.risk_grade,
        "predicted_default_yn": pred.predicted_default_yn,
        "review_comment": row.review_comment,
        "llm_model": row.llm_model,
        "created_at": row.created_at,
    }
