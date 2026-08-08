from typing import Any

import pandas as pd
from mabwiser.mab import MAB, LearningPolicy, NeighborhoodPolicy

# Static priors used until the bandit has been trained (so it can never hurt).
PRIORS = {
    "restart_pod": 0.6,
    "delete_pod": 0.5,
    "scale_deployment": 0.4,
    "rollback_deployment": 0.3,
    "cordon_node": 0.1,
}

FEATURES = [
    "is_sev1",
    "is_sev2",
    "unavailable_replicas",
    "restart_count",
    "is_deployment",
]


def build_context(state: dict) -> dict[str, Any]:
    """Deterministic context vector from incident state (consistent fit/predict)."""
    sev = state.get("severity", "SEV-3")
    metrics = state.get("metrics", {})
    kind = state.get("resource_kind", "pod").lower()
    return {
        "is_sev1": 1.0 if sev == "SEV-1" else 0.0,
        "is_sev2": 1.0 if sev == "SEV-2" else 0.0,
        "unavailable_replicas": float(metrics.get("unavailable_replicas") or 0),
        "restart_count": float(metrics.get("restart_count") or 0),
        "is_deployment": 1.0 if kind in ("deployment", "deployments", "statefulset") else 0.0,
    }


class ContextualBandit:
    def __init__(self):
        self.mab = MAB(
            arms=list(PRIORS.keys()),
            learning_policy=LearningPolicy.EpsilonGreedy(epsilon=0.1),
            neighborhood_policy=NeighborhoodPolicy.KNearest(k=5),
        )
        self.is_fitted = False

    def _ranked_from_priors(self) -> list[tuple[str, float]]:
        return sorted(PRIORS.items(), key=lambda kv: kv[1], reverse=True)

    def predict(self, context: dict):
        if not self.is_fitted:
            return "restart_pod"
        try:
            df_context = pd.DataFrame([context])
            return self.mab.predict(df_context)[0]
        except Exception:
            # Too few training samples for the neighborhood policy: fall back.
            return self._ranked_from_priors()[0][0]

    async def partial_fit(self, action: str, reward: float, context: dict):
        df_context = pd.DataFrame([context])
        self.mab.partial_fit([action], [reward], df_context)
        self.is_fitted = True

    def get_ranked_actions(self, context: dict) -> list[dict[str, Any]]:
        """Rank all arms by expected reward (priors until trained)."""
        if not self.is_fitted:
            ranked = self._ranked_from_priors()
        else:
            try:
                df = pd.DataFrame([context])
                expectations = self.mab.predict_expectations(df)
                ranked = sorted(expectations.items(), key=lambda kv: kv[1], reverse=True)
            except Exception:
                # KNearest needs k+1 samples to rank; fall back to priors.
                ranked = self._ranked_from_priors()
        return [
            {"action_type": arm, "expected_reward": float(score), "source": "bandit"}
            for arm, score in ranked
        ]


bandit = ContextualBandit()
