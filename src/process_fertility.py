from pathlib import Path
from typing import List, Union

import pandas as pd


class FertilityProcessor:
    """
    Processes fertility data to compute the average birth rate per woman per year for a given list of forecast years.
    """

    def __init__(
        self,
        fertility_data_path: Union[str, Path],
        min_preschool_age: int = 18,
        max_preschool_age: int = 6 * 12,
    ):
        """
        Initializes the FertilityProcessor.

        Args:
            fertility_data_path: The path to the fertility CSV.
            min_preschool_age: The minimum age of a preschooler in months.
            max_preschool_age: The maximum age of a preschooler in months.
        """
        self.fertility_data_path = fertility_data_path
        self.fertility_data = pd.read_csv(fertility_data_path, index_col=0)
        # Remove whitespaces from indices
        self.fertility_data.index = self.fertility_data.index.str.strip()

        self.min_preschool_age = min_preschool_age
        self.max_preschool_age = max_preschool_age

        self.mother_ages = [
            "20 - 24 Years",
            "25 - 29 Years",
            "30 - 34 Years",
            "35 - 39 Years",
        ]

    def birth_years_for_single_forecast_year(self, forecast_year: int) -> List[int]:
        """
        Computes the birth years of preschoolers for a given year.

        Args;
            forecast_year: The year to compute the birth years for.

        Returns:
            A list of birth years.
        """
        start_birth_year = forecast_year - round(self.max_preschool_age / 12)
        end_birth_year = forecast_year - round(self.min_preschool_age / 12)
        return list(range(start_birth_year, end_birth_year + 1))

    def birth_years_for_multiple_forecast_years(self, forecast_years: List[int]) -> List[int]:
        """
        Computes the birth years of preschoolers for multiple forecast years.

        Args:
            forecast_years: A list of forecast years.

        Returns:
            A list of birth years.
        """
        birth_years_all = None
        for forecast_year in forecast_years:
            if birth_years_all is None:
                birth_years_all = self.birth_years_for_single_forecast_year(
                    forecast_year
                )
            else:
                birth_years_all.append(
                    max(self.birth_years_for_single_forecast_year(forecast_year))
                )
        return birth_years_all

    def extrapolate_births(self, birth_years: List[int]) -> pd.DataFrame:
        """
        Some birth years required for forecasting may not be available in the data.
        This function extrapolates for those years by replicating from the latest available year.

        Args:
            birth_years_all: A list of birth years.

        Returns:
            A pandas DataFrame with the extrapolated births.
        """
        available_years = self.fertility_data.columns
        available_years = [int(year) for year in available_years]
        latest_available_year = max(available_years)

        if latest_available_year < max(birth_years):
            print(
                f"Extrapolating births for years {latest_available_year+1} to {max(birth_years)}"
            )
            for year in range(latest_available_year + 1, max(birth_years) + 1):
                if year not in available_years:
                    self.fertility_data[str(year)] = self.fertility_data[
                        str(latest_available_year)
                    ]

        return self.fertility_data

    def get_birth_rates_for_forecast_years(self, birth_years: List[int]) -> pd.Series:
        """
        Computes the average birth rate per woman per year for the given birth years.

        Args:
            birth_years: A list of birth years.

        Returns:
            A pandas Series with the average birth rate per woman per year.
        """
        # Birth rate by age group, per 1000 women per year
        birth_rate_by_age = self.fertility_data.loc[
            self.mother_ages, [str(year) for year in birth_years]
        ]
        # Average across age groups
        avg_birth_rate_per_woman_per_year = birth_rate_by_age.mean(axis=0) / 1000
        return avg_birth_rate_per_woman_per_year

    def run(self, forecast_years: List[int]) -> pd.Series:
        """
        Takes a list of years to forcast, and returns the average birth rate per woman per year for those years.

        Args:
            forecast_years: A list of forecast years.

        Returns:
            A pandas Series with the average birth rate per woman per year.
        """
        print(f"Processing fertility data for forecast years: {forecast_years}")
        self.birth_years = self.birth_years_for_multiple_forecast_years(forecast_years)
        print(f"Birth years: {self.birth_years}")
        
        self.fertility_data = self.extrapolate_births(self.birth_years)
        birth_rates = self.get_birth_rates_for_forecast_years(self.birth_years)
        return birth_rates


if __name__ == "__main__":
    fertility_processor = FertilityProcessor(
        fertility_data_path=Path("data/BirthsAndFertilityRatesAnnual.csv")
    )
    birth_rates = fertility_processor.run(forecast_years=[2026, 2027, 2028, 2029, 2030])
    print(birth_rates)
