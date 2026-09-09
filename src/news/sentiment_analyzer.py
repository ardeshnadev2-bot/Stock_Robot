import re
import math
from src.utils.logger import log_info, log_error

# Comprehensive Loughran-McDonald and Financial Domain Sentiment Lexicon
FINANCIAL_POSITIVE_TERMS = {
    # Earnings & Growth
    "profit": 1.5, "profits": 1.5, "profitable": 1.4, "profitability": 1.4,
    "growth": 1.3, "growing": 1.2, "surge": 1.8, "surged": 1.8, "surges": 1.8,
    "soar": 1.8, "soared": 1.8, "soars": 1.8, "rally": 1.6, "rallied": 1.6, "rallies": 1.6,
    "jump": 1.5, "jumped": 1.5, "jumps": 1.5, "gain": 1.3, "gained": 1.3, "gains": 1.4,
    "outperform": 1.8, "outperformed": 1.8, "outperforming": 1.8, "outperformance": 1.8,
    "beat": 1.6, "beats": 1.6, "exceed": 1.5, "exceeded": 1.5, "exceeds": 1.5,
    "record": 1.4, "high": 0.8, "all-time high": 2.0, "breakthrough": 1.5,
    "dividend": 1.4, "dividends": 1.4, "bonus": 1.3, "buyback": 1.4,
    "revenue": 0.8, "sales": 0.7, "turnover": 0.7,
    "expansion": 1.3, "expanded": 1.2, "expanding": 1.2, "invest": 1.0, "investment": 1.1,
    "partnership": 1.2, "deal": 1.0, "acquisition": 1.1, "alliance": 1.2, "contract": 1.1,
    "upgrade": 1.7, "upgraded": 1.7, "upgrades": 1.7, "bullish": 1.8, "bull": 1.4,
    "strong": 1.4, "robust": 1.5, "resilient": 1.4, "rebound": 1.5, "recovery": 1.4,
    "multifold": 1.7, "turnaround": 1.6, "upswing": 1.5, "optimism": 1.4,
    "windfall": 1.8, "tailwind": 1.5, "tailwinds": 1.5, "win": 1.3, "won": 1.3, "wins": 1.3
}

FINANCIAL_NEGATIVE_TERMS = {
    # Losses & Declines
    "loss": -1.6, "losses": -1.6, "slump": -1.8, "slumped": -1.8, "slumps": -1.8,
    "decline": -1.4, "declined": -1.4, "declines": -1.4, "declining": -1.3,
    "drop": -1.4, "dropped": -1.4, "drops": -1.4, "fall": -1.3, "fell": -1.4, "falls": -1.3,
    "plunge": -1.9, "plunged": -1.9, "plunges": -1.9, "tumble": -1.8, "tumbled": -1.8, "tumbles": -1.8,
    "crash": -2.0, "crashed": -2.0, "collapse": -2.0, "collapsed": -2.0,
    "miss": -1.5, "missed": -1.5, "misses": -1.5, "lag": -1.2, "lagged": -1.2,
    "underperform": -1.7, "underperformed": -1.7, "underperformance": -1.7,
    "deficit": -1.5, "debt": -1.2, "default": -2.2, "defaulted": -2.2, "bankruptcy": -2.5,
    "bankrupt": -2.5, "insolvency": -2.4, "insolvent": -2.4, "liquidation": -2.2,
    "fraud": -2.5, "scam": -2.5, "probe": -1.8, "investigation": -1.6, "investigated": -1.6,
    "penalty": -1.8, "penalized": -1.8, "fine": -1.5, "fined": -1.5, "lawsuit": -1.7,
    "sued": -1.7, "litigation": -1.5, "violation": -1.6, "curb": -1.4, "curbs": -1.4,
    "downgrade": -1.8, "downgraded": -1.8, "downgrades": -1.8, "bearish": -1.7, "bear": -1.3,
    "weak": -1.4, "weakness": -1.4, "headwind": -1.5, "headwinds": -1.5, "pessimism": -1.4,
    "slashes": -1.6, "slashed": -1.6, "cut": -1.2, "cuts": -1.2, "layoff": -1.7, "layoffs": -1.7,
    "shrink": -1.5, "shrank": -1.5, "shrunk": -1.5, "erosion": -1.6, "stagnant": -1.2
}

FINANCIAL_INTENSIFIERS = {
    "strong": 1.5, "strongly": 1.5, "sharp": 1.4, "sharply": 1.4,
    "massive": 1.6, "substantially": 1.4, "significant": 1.3, "significantly": 1.3,
    "huge": 1.5, "steep": 1.4, "steeply": 1.4, "drastic": 1.5, "drastically": 1.5
}

FINANCIAL_NEGATIONS = {
    "not", "no", "never", "hardly", "barely", "fails", "failed", "failing",
    "unable", "without", "neither", "nor"
}


class SentimentAnalyzer:
    """
    Performs financial sentiment analysis using FinBERT (when available) 
    or an enhanced Loughran-McDonald financial domain sentiment engine.
    """

    def __init__(self, model_name: str = "ProsusAI/finbert"):
        self.model_name = model_name
        self._finbert_pipeline = None
        self._finbert_initialized = False
        self._vader_analyzer = None

    def _get_vader_analyzer(self):
        """Lazy-loads VADER Sentiment Analyzer."""
        if self._vader_analyzer is None:
            try:
                from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
                self._vader_analyzer = SentimentIntensityAnalyzer()
            except Exception:
                self._vader_analyzer = False
        return self._vader_analyzer if self._vader_analyzer is not False else None

    def _get_finbert_pipeline(self):
        """
        Attempts to lazy-load the FinBERT pipeline.
        If PyTorch or transformers model weights are unavailable, returns None.
        """
        if self._finbert_initialized:
            return self._finbert_pipeline

        self._finbert_initialized = True
        try:
            import torch
            from transformers import pipeline
            log_info("sentiment_analyzer", f"Initializing FinBERT pipeline ({self.model_name})...")
            # device = -1 for CPU
            self._finbert_pipeline = pipeline(
                "sentiment-analysis",
                model=self.model_name,
                tokenizer=self.model_name,
                device=-1,
                top_k=None  # returns all score probabilities
            )
            log_info("sentiment_analyzer", "FinBERT pipeline loaded successfully.")
        except Exception as e:
            log_info("sentiment_analyzer", f"FinBERT not loaded ({str(e)}). Using financial domain sentiment engine.")
            self._finbert_pipeline = None

        return self._finbert_pipeline

    def _analyze_with_finbert(self, text: str) -> dict | None:
        """Runs FinBERT inference on the input text."""
        pipeline_obj = self._get_finbert_pipeline()
        if not pipeline_obj:
            return None

        try:
            # FinBERT operates on max 512 tokens, truncate text if long
            truncated_text = text[:1000]
            outputs = pipeline_obj(truncated_text)

            # Output is a list of dicts [{'label': 'positive', 'score': 0.91}, ...]
            scores_map = {}
            if isinstance(outputs, list):
                item_list = outputs[0] if isinstance(outputs[0], list) else outputs
                for item in item_list:
                    lbl = item["label"].lower()
                    scores_map[lbl] = float(item["score"])

            p_pos = scores_map.get("positive", 0.0)
            p_neg = scores_map.get("negative", 0.0)
            p_neu = scores_map.get("neutral", 0.0)

            # Determine dominant label
            if p_pos >= p_neg and p_pos >= p_neu:
                label = "Positive"
                score = round(p_pos, 2)
                confidence = round(p_pos * 100, 1)
            elif p_neg >= p_pos and p_neg >= p_neu:
                label = "Negative"
                score = round(-p_neg, 2)
                confidence = round(p_neg * 100, 1)
            else:
                label = "Neutral"
                score = round(p_pos - p_neg, 2)
                confidence = round(p_neu * 100, 1)

            return {
                "sentiment": label,
                "sentiment_score": score,
                "confidence": confidence
            }
        except Exception as e:
            log_error(
                module_name="sentiment_analyzer",
                error_type="FinBERTInferenceError",
                message=f"FinBERT inference failed: {str(e)}",
                action="Fallback to financial domain sentiment engine"
            )
            return None

    def _analyze_with_financial_lexicon(self, text: str) -> dict:
        """
        Analyzes text using the Loughran-McDonald financial dictionary and contextual rules,
        blended with VADER sentiment analyzer.
        """
        text_lower = text.lower()
        words = re.findall(r"\b[\w-]+\b", text_lower)

        pos_score = 0.0
        neg_score = 0.0
        negation_active = False
        negation_window = 0
        intensifier_factor = 1.0

        for idx, word in enumerate(words):
            if word in FINANCIAL_NEGATIONS:
                negation_active = True
                negation_window = 3
                continue

            if word in FINANCIAL_INTENSIFIERS:
                intensifier_factor = FINANCIAL_INTENSIFIERS[word]
                continue

            weight = 1.0 * intensifier_factor
            intensifier_factor = 1.0  # Reset after applying

            if word in FINANCIAL_POSITIVE_TERMS:
                val = FINANCIAL_POSITIVE_TERMS[word] * weight
                if negation_active:
                    neg_score += val  # Negated positive becomes negative
                else:
                    pos_score += val
            elif word in FINANCIAL_NEGATIVE_TERMS:
                val = abs(FINANCIAL_NEGATIVE_TERMS[word]) * weight
                if negation_active:
                    pos_score += val * 0.5  # Negated negative becomes mildly positive
                else:
                    neg_score += val

            if negation_window > 0:
                negation_window -= 1
                if negation_window == 0:
                    negation_active = False

        # Check multi-word financial phrases
        if "profit growth" in text_lower or "strong quarterly" in text_lower:
            pos_score += 2.0
        if "earnings beat" in text_lower or "beats estimates" in text_lower:
            pos_score += 2.0
        if "all-time high" in text_lower or "record high" in text_lower:
            pos_score += 2.0
        if "quarterly loss" in text_lower or "profit drops" in text_lower or "profit slump" in text_lower:
            neg_score += 2.0
        if "misses estimates" in text_lower or "slashes guidance" in text_lower:
            neg_score += 2.0
        if "regulatory probe" in text_lower or "accounting fraud" in text_lower:
            neg_score += 2.5

        # Incorporate VADER if available
        vader = self._get_vader_analyzer()
        vader_compound = 0.0
        if vader:
            try:
                vs = vader.polarity_scores(text)
                vader_compound = vs.get("compound", 0.0)
            except Exception:
                pass

        # Calculate net domain score
        total_signal = pos_score + neg_score
        if total_signal > 0:
            diff = pos_score - neg_score
            # Normalize using hyperbolic tangent or sigmoid-like scaling
            lexicon_score = math.tanh(diff / 2.5)
        else:
            lexicon_score = vader_compound

        # Blend financial lexicon (80%) and VADER (20%)
        final_score = (0.80 * lexicon_score) + (0.20 * vader_compound) if total_signal > 0 else vader_compound
        final_score = max(-1.0, min(1.0, final_score))

        # Classification thresholds
        if final_score >= 0.15:
            sentiment = "Positive"
            confidence = min(98.0, max(65.0, 55.0 + (abs(final_score) * 40.0)))
        elif final_score <= -0.15:
            sentiment = "Negative"
            confidence = min(98.0, max(65.0, 55.0 + (abs(final_score) * 40.0)))
        else:
            sentiment = "Neutral"
            # Neutral confidence is high when score is close to 0 with few conflicting signals
            neutrality = 1.0 - abs(final_score)
            confidence = round(min(90.0, max(60.0, neutrality * 75.0)), 1)

        # Example headline test: "Company reports strong quarterly profit growth"
        # Should output Positive, score ~ +0.82, confidence ~ 91%
        return {
            "sentiment": sentiment,
            "sentiment_score": round(final_score, 2),
            "confidence": round(confidence, 1)
        }

    def analyze(self, headline: str, description: str = "") -> dict:
        """
        Analyzes the Headline + Description of a news article.
        
        Args:
            headline (str): Article title / headline.
            description (str, optional): Article summary or description.
            
        Returns:
            dict:
                - sentiment (str): 'Positive', 'Negative', or 'Neutral'
                - sentiment_score (float): Score between -1.0 and +1.0
                - confidence (float): Percentage between 0 and 100
        """
        combined_text = f"{headline.strip()} {description.strip()}".strip()
        if not combined_text:
            return {
                "sentiment": "Neutral",
                "sentiment_score": 0.0,
                "confidence": 50.0
            }

        try:
            # 1. Attempt FinBERT analysis if configured and loaded
            finbert_result = self._analyze_with_finbert(combined_text)
            if finbert_result:
                return finbert_result

            # 2. Fallback to Financial Domain Lexicon engine
            return self._analyze_with_financial_lexicon(combined_text)

        except Exception as e:
            log_error(
                module_name="sentiment_analyzer",
                error_type="SentimentAnalysisError",
                message=f"Sentiment analysis encountered unexpected error: {str(e)}",
                action="Return safe Neutral default"
            )
            return {
                "sentiment": "Neutral",
                "sentiment_score": 0.0,
                "confidence": 50.0
            }
