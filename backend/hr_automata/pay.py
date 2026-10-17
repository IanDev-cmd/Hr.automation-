"""Location sleep-in rates for Mayfield, Rainbow, and Fernleigh."""

from typing import Any, Dict


class PayAndAllowanceCalculator:
    """Annual package from the £27,300 / £14.00 base plus sleep-ins.

    Mayfield Lodge and Rainbow Lodge are Bournemouth (£63 a night).
    Fernleigh House is Cornwall (£60 a night). £14 × 37.5 × 52 = £27,300,
    so bank staff and full-time share the same annual base.
    """

    SLEEP_IN_RATES = {
        "Mayfield Lodge": 63.00,
        "Rainbow Lodge": 63.00,
        "Fernleigh House": 60.00,
    }
    BASE_ANNUAL_SALARY = 27300.00
    HOURLY_RATE = 14.00

    def calculate_offer_package(
        self,
        home_name: str,
        expected_sleep_ins_per_week: int = 2,
        employment_type: str = "Full-time",
    ) -> Dict[str, Any]:
        if expected_sleep_ins_per_week < 0:
            raise ValueError("expected sleep-ins cannot be negative")
        sleep_in_rate = self.SLEEP_IN_RATES.get(home_name, 63.00)
        annual_sleep_ins = expected_sleep_ins_per_week * 52
        annual_sleep_in_pay = annual_sleep_ins * sleep_in_rate
        total_gross_package = self.BASE_ANNUAL_SALARY + annual_sleep_in_pay
        region = "Cornwall" if home_name == "Fernleigh House" else "Bournemouth"

        return {
            "home_location": home_name,
            "region": region,
            "employment_type": employment_type,
            "base_hourly_rate": self.HOURLY_RATE,
            "base_annual_salary": self.BASE_ANNUAL_SALARY,
            "sleep_in_rate_per_night": sleep_in_rate,
            "projected_sleep_ins_annual": annual_sleep_ins,
            "annual_sleep_in_allowance": annual_sleep_in_pay,
            "total_gross_annual_package": round(total_gross_package, 2),
        }
