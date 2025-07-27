from pathlib import Path
from typing import List, Union

import pandas as pd


class BTOProcessor:
    """
    Processes BTO data to compute the number of BTO units completed per subzone per year.
    """

    def __init__(self, bto_data_path: Union[str, Path]) -> None:
        self.bto_data = pd.read_csv(bto_data_path)

    def get_cumulative_bto_units_by_subzone(self, years: List[int]) -> pd.DataFrame:
        """
        Computes the cumulative number of BTO units completed per subzone for the given years.

        Args:
            years: A list of years of completion.

        Returns:
            A pandas DataFrame with the cumulative number of BTO units completed per subzone up to each year.
            Rows are the years of completion, and columns are the subzones.
        """
        # Subset to only include BTOs that are completed by the end of the forecast period
        bto_data_for_forecast = self.bto_data[
            self.bto_data["Estimated completion year"] <= max(years)
        ]

        bto_units_by_subzone = pd.pivot_table(
            bto_data_for_forecast,
            values="Total number of units",
            index="Subzone",
            columns="Estimated completion year",
            aggfunc="sum",
            fill_value=0,
        ).cumsum(axis=1)

        bto_units_by_subzone.columns = bto_units_by_subzone.columns.astype(str)
        bto_units_by_subzone = bto_units_by_subzone.transpose()

        # Remove whitespace from subzone names
        bto_units_by_subzone.columns = bto_units_by_subzone.columns.str.strip()

        return bto_units_by_subzone

    def run(self, years: List[int]) -> pd.DataFrame:
        """
        Computes the cumulative number of BTO units completed per subzone for the given years.

        Args:
            years: A list of years of completion.

        Returns:
            A pandas DataFrame with the cumulative number of BTO units completed per subzone up to each year.
            Rows are the years of completion, and columns are the subzones.
        """
        print(f"Computing cumulative BTO units for years: {years}")
        return self.get_cumulative_bto_units_by_subzone(years)


if __name__ == "__main__":
    bto_processor = BTOProcessor(bto_data_path=Path("data/btomapping.csv"))
    bto_units_by_subzone = bto_processor.run(
        [2020, 2021, 2022, 2023, 2024, 2025, 2026, 2027, 2028]
    )
    print(bto_units_by_subzone)
