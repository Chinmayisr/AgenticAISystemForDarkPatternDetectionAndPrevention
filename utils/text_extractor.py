# utils/text_extractor.py

import re
from typing import List, Dict


class TextExtractor:
    """
    Cleans and structures raw webpage text content for NLP analysis.
    Splits into logical segments so the agent can analyze each section.
    """

    # Maximum characters per chunk sent to the agent
    CHUNK_SIZE = 3000

    def load_from_file(self, file_path: str) -> str:
        """Read raw text from input file."""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def clean(self, raw_text: str) -> str:
        """Remove noise from raw extracted webpage text."""
        # Remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', raw_text)
        text = re.sub(r' {2,}', ' ', text)
        # Remove pure separator lines (===, ---, ...)
        text = re.sub(r'^[=\-_\*]{3,}$', '', text, flags=re.MULTILINE)
        # Strip leading/trailing whitespace per line
        lines = [line.strip() for line in text.splitlines()]
        text = '\n'.join(line for line in lines if line)
        return text.strip()

    def extract_segments(self, text: str) -> List[Dict]:
        """
        Split webpage text into labeled segments.
        Each segment is a logical unit (banner, button, form, etc.)
        that the agent will analyze independently.
        """
        segments = []

        # Define segment patterns based on common webpage structure keywords
        section_markers = [
            (r'(?:URGENCY|DEAL|SALE|TIMER|BANNER|FLASH)', 'urgency_banner'),
            (r'(?:BUTTON|CTA|ACTION|CLICK)', 'button_text'),
            (r'(?:SUBSCRIPTION|SUBSCRIBE|AUTO.?RENEW)', 'subscription'),
            (r'(?:CHECKBOX|CONSENT|AGREE|OPT)', 'consent_form'),
            (r'(?:RECOMMENDED|TOP PICK|FEATURED|SPONSORED|ADS?)', 'advertisement'),
            (r'(?:PRICE|COST|FEE|TOTAL|CHECKOUT)', 'pricing'),
            (r'(?:NAVIGATION|NAV|MENU|HEADER)', 'navigation'),
            (r'(?:FOOTER|CONTACT|ABOUT)', 'footer'),
        ]

        lines = text.splitlines()
        current_segment = {"type": "general", "lines": []}

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if this line is a section header
            matched_type = None
            for pattern, seg_type in section_markers:
                if re.search(pattern, line, re.IGNORECASE):
                    matched_type = seg_type
                    break

            if matched_type and len(line) < 60:
                # Save previous segment
                if current_segment["lines"]:
                    segments.append({
                        "type": current_segment["type"],
                        "text": '\n'.join(current_segment["lines"])
                    })
                # Start new segment
                current_segment = {"type": matched_type, "lines": [line]}
            else:
                current_segment["lines"].append(line)

        # Don't forget the last segment
        if current_segment["lines"]:
            segments.append({
                "type": current_segment["type"],
                "text": '\n'.join(current_segment["lines"])
            })

        return [s for s in segments if len(s["text"].strip()) > 10]

    def extract_high_risk_lines(self, text: str) -> List[str]:
        """
        Pull out individual lines most likely to contain dark patterns.
        Used to give the agent focused, line-level evidence.
        """
        high_risk = []
        patterns = [
            # False Urgency
            r'\bonly \d+\s*(left|remaining|in stock)\b',
            r'\b\d+\s*people\s*(are\s*)?(viewing|watching|looking)',
            r'\b(hurry|act now|ends? in|limited time|flash sale|selling fast)\b',
            r'\d+:\d+:\d+',                            # countdown timer format
            r'\b(last chance|almost gone|nearly sold out)\b',
            # Confirm Shaming
            r"no[,\s]+(thanks?|i)[,\s]+i\s+(hate|don'?t want|prefer not)",
            r"no[,\s]+i\s+(don'?t|do not)\s+want",
            r"(skip|decline)[^.]*i\s+(don'?t|prefer not|hate)",
            # Forced Action
            r'\b(share with|invite)\s+\d+\s+(friends?|people)',
            r'\b(must|required|mandatory)\s+(create|sign up|register|download)',
            r'\bdownload (our|the) app\b',
            r'\benter your (phone|mobile|email) to\b',
            # Trick Questions
            r'(uncheck|deselect).{0,40}(not|don\'?t|no)',
            r'(not|don\'?t).{0,20}(not|don\'?t).{0,20}(receive|share|send)',
            r'check.{0,30}prevent.{0,30}not',
            # Disguised Ads
            r'(sponsored|paid|advertisement|promoted)',
            r'(top picks?|recommended for you|featured).{0,50}paid',
        ]

        for line in text.splitlines():
            line = line.strip()
            if any(re.search(p, line, re.IGNORECASE) for p in patterns):
                if line not in high_risk and len(line) > 5:
                    high_risk.append(line)

        return high_risk