# utils/behavioral_analyzer.py

from typing import Dict, List
from datetime import datetime


class BehavioralAnalyzer:
    """
    Pre-processes behavioral JSON input and computes all derived
    signals before the agent runs. Gives the agent clean numbers
    and flags rather than raw event arrays to reason about.
    """

    def load(self, file_path: str) -> dict:
        import json
        from pathlib import Path
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Not found: {file_path}")
        if path.suffix.lower() != ".json":
            raise ValueError(f"Expected .json, got: {path.suffix}")
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def compute_context(self, data: dict) -> dict:
        """
        Run all pre-analysis computations and return a structured
        context dict the agent uses as its starting point.
        """
        ctx = {
            "platform":    data.get("platform", "unknown"),
            "session_id":  data.get("session_id", ""),
            "url":         data.get("url", ""),
            "basket_sneaking":   self._analyze_basket_sneaking(data),
            "subscription_trap": self._analyze_subscription_trap(data),
            "saas_billing":      self._analyze_saas_billing(data),
            "nagging":           self._analyze_nagging(data),
        }
        ctx["active_checks"] = [
            k for k in ["basket_sneaking","subscription_trap","saas_billing","nagging"]
            if ctx[k]["has_data"]
        ]
        return ctx

    # ── Basket Sneaking Analysis ────────────────────────────────────────────

    def _analyze_basket_sneaking(self, data: dict) -> dict:
        events     = data.get("cart_events", [])
        checkboxes = data.get("page_checkboxes", [])

        if not events and not checkboxes:
            return {"has_data": False}

        sneaked_items    = []
        event_violations = []

        # Check each cart event for unauthorized additions
        for evt in events:
            before = {i["name"]: i for i in evt.get("cart_before", [])}
            after  = {i["name"]: i for i in evt.get("cart_after",  [])}
            action = evt.get("user_action") or {}
            action_type     = action.get("type", "")
            explicitly_added = action.get("item")

            new_items = set(after.keys()) - set(before.keys())
            for item_name in new_items:
                item = after[item_name]
                # Mark as sneaked if: not explicitly added by user click
                is_sneaked = (
                    action_type != "add_to_cart" or
                    (action_type == "add_to_cart" and explicitly_added != item_name)
                )
                if is_sneaked or item.get("added_by") == "system":
                    sneaked_items.append({
                        "item_name":     item_name,
                        "price":         item.get("price", 0),
                        "added_by":      item.get("added_by", "unknown"),
                        "trigger_action": action_type,
                        "event_id":      evt.get("event_id"),
                        "timestamp":     evt.get("timestamp"),
                    })
                    event_violations.append(evt.get("event_id"))

        # Check pre-ticked checkboxes for paid items
        prechecked_paid = [
            cb for cb in checkboxes
            if cb.get("pre_checked") and not cb.get("user_changed")
        ]

        # Compute totals
        sneaked_total = sum(i["price"] for i in sneaked_items)
        recurring     = [i for i in sneaked_items if "month" in i["item_name"].lower()
                         or "year" in i["item_name"].lower()
                         or "subscription" in i["item_name"].lower()
                         or "trial" in i["item_name"].lower()]

        return {
            "has_data":              len(events) > 0 or len(checkboxes) > 0,
            "total_cart_events":     len(events),
            "sneaked_items":         sneaked_items,
            "sneaked_count":         len(sneaked_items),
            "sneaked_total_value":   round(sneaked_total, 2),
            "recurring_items":       recurring,
            "prechecked_paid_boxes": prechecked_paid,
            "event_violations":      list(set(event_violations)),
            "triggered":             len(sneaked_items) > 0 or len(prechecked_paid) > 0,
            "severity": (
                "high"   if any(i["price"] > 50 or recurring for i in sneaked_items) else
                "medium" if sneaked_total > 0 else
                "low"    if prechecked_paid else
                "none"
            )
        }

    # ── Subscription Trap Analysis ─────────────────────────────────────────

    def _analyze_subscription_trap(self, data: dict) -> dict:
        flow = data.get("subscription_flow")
        if not flow:
            return {"has_data": False}

        signup       = flow.get("signup_flow", {})
        cancellation = flow.get("cancellation_flow", {})

        signup_steps = signup.get("total_steps", 0)
        cancel_steps = cancellation.get("total_steps", 0)
        step_ratio   = round(cancel_steps / signup_steps, 2) if signup_steps > 0 else 0

        disclosure   = signup.get("auto_renewal_disclosure", {})
        trial        = signup.get("free_trial", {})

        flags = []
        if step_ratio >= 2.0:
            flags.append(f"Cancellation is {step_ratio}x harder than signup ({cancel_steps} vs {signup_steps} steps)")
        if not trial.get("conversion_reminder_sent", True):
            flags.append("No reminder sent before free trial converts to paid")
        if trial.get("trial_end_action") == "auto_convert_to_paid":
            flags.append("Trial silently auto-converts to paid subscription")
        if disclosure.get("prominence") in ("very_low", "low"):
            flags.append(f"Auto-renewal disclosure prominence: {disclosure.get('prominence')}")
        if cancellation.get("retention_popups_shown", 0) > 0:
            flags.append(f"{cancellation['retention_popups_shown']} retention popup(s) shown before cancel completes")
        if cancellation.get("mandatory_survey"):
            flags.append("Mandatory reason survey required before cancellation")
        if cancellation.get("cancel_button_visibility") == "buried":
            flags.append(f"Cancel button buried at: {cancellation.get('cancel_button_location', 'unknown path')}")

        return {
            "has_data":                  True,
            "signup_steps":              signup_steps,
            "cancellation_steps":        cancel_steps,
            "step_ratio":                step_ratio,
            "step_ratio_exceeds_2x":     step_ratio >= 2.0,
            "auto_renewal_prominence":   disclosure.get("prominence", "unknown"),
            "auto_renewal_text":         disclosure.get("text", ""),
            "trial_reminder_sent":       trial.get("conversion_reminder_sent", False),
            "trial_auto_converts":       trial.get("trial_end_action") == "auto_convert_to_paid",
            "retention_popups":          cancellation.get("retention_popups_shown", 0),
            "mandatory_survey":          cancellation.get("mandatory_survey", False),
            "cancel_visibility":         cancellation.get("cancel_button_visibility", "unknown"),
            "cancel_path":               cancellation.get("cancel_button_location", ""),
            "flags":                     flags,
            "flag_count":                len(flags),
            "triggered":                 len(flags) >= 2,
            "severity": (
                "high"   if step_ratio >= 2.0 and not trial.get("conversion_reminder_sent", True) else
                "high"   if step_ratio >= 3.0 else
                "medium" if step_ratio >= 1.5 or not trial.get("conversion_reminder_sent", True) else
                "low"    if len(flags) >= 1 else
                "none"
            )
        }

    # ── SaaS Billing Analysis ──────────────────────────────────────────────

    def _analyze_saas_billing(self, data: dict) -> dict:
        billing = data.get("billing_data")
        if not billing:
            return {"has_data": False}

        upgrade_clicks   = billing.get("upgrade_clicks", 1)
        downgrade_clicks = billing.get("downgrade_clicks", 1)
        click_ratio      = round(downgrade_clicks / upgrade_clicks, 2) if upgrade_clicks > 0 else 0
        billing_clicks   = billing.get("billing_clicks_required", 1)
        unexpected       = billing.get("unexpected_charges", [])
        unnotified       = [c for c in unexpected if not c.get("notified", True)]

        flags = []
        if not billing.get("pre_renewal_reminder", True):
            flags.append("No pre-renewal reminder sent before auto-charge")
        if billing_clicks > 3:
            flags.append(f"Billing settings require {billing_clicks} clicks to access")
        if click_ratio >= 3.0:
            flags.append(f"Downgrade is {click_ratio}x harder than upgrade ({downgrade_clicks} vs {upgrade_clicks} clicks)")
        if billing.get("downgrade_requires_support"):
            flags.append("Downgrading requires contacting support (not self-service)")
        if not billing.get("current_charges_visible_on_dashboard", True):
            flags.append("Current subscription cost not visible on main dashboard")
        if unnotified:
            total = sum(c.get("amount", 0) for c in unnotified)
            flags.append(f"{len(unnotified)} unexpected charge(s) with no notification (total: {total})")

        return {
            "has_data":                        True,
            "plan_name":                       billing.get("plan_name", ""),
            "amount_per_cycle":                billing.get("amount_per_cycle", 0),
            "billing_cycle":                   billing.get("billing_cycle", ""),
            "auto_renewal":                    billing.get("auto_renewal", False),
            "pre_renewal_reminder":            billing.get("pre_renewal_reminder", False),
            "billing_clicks_required":         billing_clicks,
            "upgrade_clicks":                  upgrade_clicks,
            "downgrade_clicks":                downgrade_clicks,
            "upgrade_downgrade_ratio":         click_ratio,
            "ratio_exceeds_3x":                click_ratio >= 3.0,
            "downgrade_requires_support":      billing.get("downgrade_requires_support", False),
            "charges_visible_on_dashboard":    billing.get("current_charges_visible_on_dashboard", True),
            "unexpected_charges":              unexpected,
            "unnotified_charges":              unnotified,
            "unnotified_total":                round(sum(c.get("amount", 0) for c in unnotified), 2),
            "flags":                           flags,
            "flag_count":                      len(flags),
            "triggered":                       len(flags) >= 1,
            "severity": (
                "high"   if unnotified and click_ratio >= 3.0 else
                "high"   if unnotified else
                "medium" if not billing.get("pre_renewal_reminder") or click_ratio >= 3.0 else
                "low"    if len(flags) >= 1 else
                "none"
            )
        }

    # ── Nagging Analysis ───────────────────────────────────────────────────

    def _analyze_nagging(self, data: dict) -> dict:
        popup_events = data.get("popup_events", [])
        if not popup_events:
            return {"has_data": False}

        # Group events by popup_id
        by_id: Dict[str, list] = {}
        for evt in popup_events:
            pid = evt.get("popup_id", "unknown")
            by_id.setdefault(pid, []).append(evt)

        nagging_popups = []
        for popup_id, events in by_id.items():
            appearances    = len(events)
            dismissed_count = sum(1 for e in events if e.get("user_dismissed"))
            popup_type     = events[0].get("popup_type", "unknown")
            reappeared     = any(e.get("reappeared") for e in events)
            sample_text    = events[0].get("text", "")

            # Check for cookie consent ignored
            cookie_ignored = (
                popup_type == "cookie_consent" and
                any(e.get("user_choice") == "rejected_all" for e in events) and
                reappeared
            )

            # Severity determination
            if appearances >= 3 or cookie_ignored or (
                popup_type == "push_notification_request" and appearances >= 2
            ):
                severity = "high"
            elif appearances == 2 and dismissed_count >= 1 and reappeared:
                severity = "medium"
            else:
                severity = "low"

            if appearances >= 2 or reappeared:
                nagging_popups.append({
                    "popup_id":       popup_id,
                    "popup_type":     popup_type,
                    "appearances":    appearances,
                    "dismissed_count": dismissed_count,
                    "reappeared_after_dismiss": reappeared and dismissed_count > 0,
                    "cookie_consent_ignored":   cookie_ignored,
                    "sample_text":    sample_text,
                    "severity":       severity,
                })

        total_appearances = sum(p["appearances"] for p in nagging_popups)
        high_count        = sum(1 for p in nagging_popups if p["severity"] == "high")

        return {
            "has_data":            len(popup_events) > 0,
            "total_popup_events":  len(popup_events),
            "unique_popups":       len(by_id),
            "nagging_popups":      nagging_popups,
            "nagging_count":       len(nagging_popups),
            "total_reappearances": total_appearances,
            "high_severity_count": high_count,
            "triggered":           len(nagging_popups) > 0,
            "overall_severity": (
                "high"   if high_count >= 2 else
                "high"   if any(p["cookie_consent_ignored"] for p in nagging_popups) else
                "medium" if len(nagging_popups) >= 1 else
                "none"
            )
        }