from pathlib import Path
from typing import Union, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
import argparse

import pandas as pd

from src.process_fertility import FertilityProcessor
from src.process_bto import BTOProcessor
from src.process_preschools import PreschoolProcessor
from src.process_existing_residents import ExistingResidentsProcessor


@dataclass
class Config:
    # Forecaster
    num_forecast_years: int = 5
    preschool_capacity: int = 100
    current_year = datetime.now().year

    # FertilityProcessor
    fertility_data_path: Union[str, Path] = Path(
        "data/BirthsAndFertilityRatesAnnual.csv"
    )
    min_preschool_age: int = 18
    max_preschool_age: int = 6 * 12

    # BTOProcessor
    bto_data_path: Union[str, Path] = Path("data/btomapping.csv")

    # PreschoolProcessor
    subzone_data_path: Union[str, Path] = Path(
        "data/Master Plan 2019 Subzone Boundary (No Sea) (GEOJSON).geojson"
    )
    crs: str = "urn:ogc:def:crs:OGC:1.3:CRS84"
    raw_preschool_data_path: Union[str, Path] = Path("data/ListingofCentres.csv")
    processed_preschool_data_path: Optional[Union[str, Path]] = Path(
        "data/preschools_data_processed.csv"
    )

    # ExistingResidentsProcessor
    existing_residents_path: Union[str, Path] = Path(
        "data/respopagesex2000to2020e.xlsx"
    )
    sheet_name: str = "2020"
    header_row: int = 2


class Forecaster:
    """
    Takes in processed fertility, BTO, existing residents and preschool data, and forecasts
    the number of preschools in each subzone for the given forecast years.
    """

    def __init__(self, config: Config) -> None:
        self.config = config

        self.fertility_processor = FertilityProcessor(
            fertility_data_path=config.fertility_data_path,
            min_preschool_age=config.min_preschool_age,
            max_preschool_age=config.max_preschool_age,
        )
        self.bto_processor = BTOProcessor(bto_data_path=config.bto_data_path)
        self.existing_residents_processor = ExistingResidentsProcessor(
            existing_residents_path=config.existing_residents_path,
            sheet_name=config.sheet_name,
            header_row=config.header_row,
        )
        self.preschool_processor = PreschoolProcessor(
            subzone_data_path=config.subzone_data_path,
            crs=config.crs,
            raw_preschool_data_path=config.raw_preschool_data_path,
            processed_preschool_data_path=config.processed_preschool_data_path,
        )

        self.current_year = config.current_year
        self.forecast_years = list(
            range(
                self.current_year + 1, self.current_year + 1 + config.num_forecast_years
            )
        )

    def calculate_existing_preschoolers_for_year(
        self,
        target_year: int,
        fertility_rates_by_age: pd.DataFrame,
        existing_women_by_age_bin: pd.DataFrame,
    ) -> pd.Series:
        """Calculate preschoolers born to existing women in each subzone for a specific forecast year.

        Args:
            target_year: The year to calculate preschoolers for.
            fertility_rates_by_age: DataFrame with age-specific fertility rates by year.
            existing_women_by_age_bin: DataFrame with women counts by subzone and age bin.

        Returns:
            Series with preschooler counts by subzone.
        """
        birth_years_for_target = (
            self.fertility_processor.birth_years_for_single_forecast_year(target_year)
        )

        # Initialize result series for each subzone - ensure unique subzones
        all_subzones = existing_women_by_age_bin["Subzone"].unique()
        # Convert to list and back to ensure clean unique values
        all_subzones = list(set(all_subzones))
        subzone_preschoolers = pd.Series(0.0, index=all_subzones)

        for birth_year in birth_years_for_target:
            birth_year_str = str(birth_year)

            if birth_year_str in fertility_rates_by_age.columns:
                # Get age-specific fertility rates for this birth year (per 1000 women)
                fertility_rates_for_year = fertility_rates_by_age[birth_year_str] / 1000

                # For each subzone, calculate births from existing women
                for subzone in all_subzones:
                    subzone_data = existing_women_by_age_bin[
                        existing_women_by_age_bin["Subzone"] == subzone
                    ]

                    total_births_in_subzone = 0

                    # Apply age-specific fertility rates to women in each age group
                    for age_bin in self.existing_residents_processor.all_mother_ages:
                        women_in_age_bin = subzone_data[
                            subzone_data["Age Bin"] == age_bin
                        ]["Count"].sum()

                        if (
                            women_in_age_bin > 0
                            and age_bin in fertility_rates_for_year.index
                        ):
                            fertility_rate = fertility_rates_for_year[age_bin]
                            births_from_age_group = women_in_age_bin * fertility_rate
                            total_births_in_subzone += births_from_age_group

                    # For most recent birth year, only count half (born early in year)
                    if birth_year == max(birth_years_for_target):
                        total_births_in_subzone *= 0.5

                    subzone_preschoolers[subzone] += total_births_in_subzone

        # Clean up results and ensure no duplicates
        subzone_preschoolers = subzone_preschoolers.fillna(0)
        subzone_preschoolers = subzone_preschoolers.astype(int)

        # Remove any potential duplicates by grouping and summing
        if subzone_preschoolers.index.duplicated().any():
            subzone_preschoolers = subzone_preschoolers.groupby(
                subzone_preschoolers.index
            ).sum()

        # TODO: allow for mothers ageing through age groups
        # Not a big issue for current forecast window

        return subzone_preschoolers

    def calculate_bto_preschoolers_for_year(
        self,
        target_year: int,
        birth_rates: pd.Series,
        bto_units_by_subzone: pd.DataFrame,
    ) -> pd.Series:
        """Calculate preschoolers born to BTO mothers in each subzone for a specific forecast year.

        Args:
            target_year: The year to calculate preschoolers for.
            birth_rates: Series of averaged birth rates for each year (births per woman per year).
            bto_units_by_subzone: DataFrame of completed BTO units (rows=years, columns=subzones).

        Returns:
            Series with preschooler counts by subzone.
        """
        birth_years_for_target = (
            self.fertility_processor.birth_years_for_single_forecast_year(target_year)
        )
        # Ensure unique column names for the index
        unique_subzones = list(set(bto_units_by_subzone.columns))
        subzone_preschoolers = pd.Series(0.0, index=unique_subzones)

        for birth_year in birth_years_for_target:
            birth_year_str = str(birth_year)

            if birth_year_str in bto_units_by_subzone.index:
                # BTO units available when these children were born
                bto_units = bto_units_by_subzone.loc[birth_year_str]

                # Children per woman in this birth year
                fertility_rate = birth_rates[birth_year_str]

                # Children born = BTO units × fertility rate
                children_from_birth_year = bto_units * fertility_rate

                # For most recent birth year, only count only children born before
                # the minimum preschool age
                if (
                    birth_year == max(birth_years_for_target)
                    and self.config.min_preschool_age % 12 != 0
                ):
                    children_from_birth_year = (
                        children_from_birth_year
                        * (12 - self.config.min_preschool_age % 12)
                        / 12
                    )

                # Ensure the children_from_birth_year Series has unique index
                if children_from_birth_year.index.duplicated().any():
                    children_from_birth_year = children_from_birth_year.groupby(children_from_birth_year.index).sum()

                # Safely add values, ensuring we're adding scalars not arrays
                for subzone in unique_subzones:
                    if subzone in children_from_birth_year.index:
                        # Get the value and ensure it's a scalar
                        value_to_add = children_from_birth_year[subzone]
                        # If it's a Series (due to duplicates), sum it
                        if hasattr(value_to_add, 'sum'):
                            value_to_add = float(value_to_add.sum())
                        else:
                            value_to_add = float(value_to_add)
                        
                        subzone_preschoolers[subzone] += value_to_add

        subzone_preschoolers = subzone_preschoolers.fillna(0)
        subzone_preschoolers = subzone_preschoolers.astype(int)
        
        # Remove any potential duplicates by grouping and summing
        if subzone_preschoolers.index.duplicated().any():
            subzone_preschoolers = subzone_preschoolers.groupby(subzone_preschoolers.index).sum()

        return subzone_preschoolers

    def calculate_preschoolers_for_year(
        self,
        target_year: int,
        bto_birth_rates: pd.Series,
        bto_units_by_subzone: pd.DataFrame,
        fertility_rates_by_age: pd.DataFrame,
        existing_women_by_age_bin: pd.DataFrame,
    ) -> pd.Series:
        """Calculate total preschoolers in each subzone for a specific forecast year.

        Args:
            target_year: The year to calculate preschoolers for.
            bto_birth_rates: Series of averaged birth rates for BTO mothers.
            bto_units_by_subzone: DataFrame of completed BTO units.
            fertility_rates_by_age: DataFrame with age-specific fertility rates by year.
            existing_women_by_age_bin: DataFrame with women counts by subzone and age bin.

        Returns:
            Series with total preschooler counts by subzone.
        """
        # Calculate preschoolers from existing residents
        existing_preschoolers = self.calculate_existing_preschoolers_for_year(
            target_year, fertility_rates_by_age, existing_women_by_age_bin
        )

        # Calculate preschoolers from BTO mothers
        bto_preschoolers = self.calculate_bto_preschoolers_for_year(
            target_year, bto_birth_rates, bto_units_by_subzone
        )

        # Ensure both Series are clean with no duplicates
        if existing_preschoolers.index.duplicated().any():
            existing_preschoolers = existing_preschoolers.groupby(existing_preschoolers.index).sum()
        
        if bto_preschoolers.index.duplicated().any():
            bto_preschoolers = bto_preschoolers.groupby(bto_preschoolers.index).sum()

        # Combine both sources using a more robust approach
        all_subzones = list(set(existing_preschoolers.index) | set(bto_preschoolers.index))
        total_preschoolers = pd.Series(0, index=all_subzones, dtype=int)

        # Add existing preschoolers
        for subzone in existing_preschoolers.index:
            if subzone in total_preschoolers.index:
                total_preschoolers[subzone] += int(existing_preschoolers[subzone])

        # Add BTO preschoolers
        for subzone in bto_preschoolers.index:
            if subzone in total_preschoolers.index:
                total_preschoolers[subzone] += int(bto_preschoolers[subzone])

        return total_preschoolers

    def calculate_preschoolers_all_years(
        self,
        bto_birth_rates: pd.Series,
        bto_units_by_subzone: pd.DataFrame,
        fertility_rates_by_age: pd.DataFrame,
        existing_women_by_age_bin: pd.DataFrame,
    ) -> pd.DataFrame:
        """Calculate preschoolers for all forecast years from both existing and BTO residents.

        Args:
            bto_birth_rates: Series of averaged birth rates for BTO mothers.
            bto_units_by_subzone: DataFrame of completed BTO units.
            fertility_rates_by_age: DataFrame with age-specific fertility rates by year.
            existing_women_by_age_bin: DataFrame with women counts by subzone and age bin.

        Returns:
            DataFrame with total preschooler projections by year and subzone.
        """
        print("TOTAL PRESCHOOLER PROJECTIONS BY YEAR (EXISTING + BTO)")
        print("=" * 60)

        # Dictionary to store results for each year
        results_by_year = {}

        # Loop through each forecast year
        for forecast_year in self.forecast_years:
            print(f"\nForecasting total preschoolers for {forecast_year}")

            # Calculate total preschoolers for this year
            preschoolers = self.calculate_preschoolers_for_year(
                forecast_year,
                bto_birth_rates,
                bto_units_by_subzone,
                fertility_rates_by_age,
                existing_women_by_age_bin,
            )

            # Store results
            results_by_year[forecast_year] = preschoolers

        # Convert to DataFrame (rows = years, columns = subzones)
        preschoolers_df = pd.DataFrame(results_by_year).T

        # Fill any missing values with 0
        preschoolers_df = preschoolers_df.fillna(0)

        # Overall summary by year
        print(f"\nTotal preschoolers by year:")
        yearly_totals = preschoolers_df.sum(axis=1)
        for year, total in yearly_totals.items():
            print(f"  {year}: {total:,.0f}")

        return preschoolers_df

    def calculate_preschool_gap(
        self,
        existing_preschools: pd.DataFrame,
        forecasted_preschools_needed: pd.DataFrame,
    ) -> pd.DataFrame:
        """Calculate the gap between the number of preschools needed and the number
        of preschools available.

        Args:
            existing_preschools: A pandas DataFrame of existing preschools by subzone.
                Rows are subzones, and there must be a "num_preschools" column.
            forecasted_preschools_needed: A pandas DataFrame of the number of preschools
                needed by subzone. Rows are years, columns are subzones.

        Returns:
            A pandas DataFrame of the gap between the number of preschools needed
                and the number of preschools available. Rows are years, columns are
                subzones. Positive values indicate a surplus, negative values indicate
                a shortage.
        """
        preschool_gap = forecasted_preschools_needed.copy()
        common_subzones = list(
            set(existing_preschools.index) & set(preschool_gap.columns)
        )

        for year in preschool_gap.index:
            for subzone in common_subzones:
                preschool_gap.loc[year, subzone] = (
                    existing_preschools.loc[subzone, "num_preschools"]
                    - preschool_gap.loc[year, subzone]
                )

        return preschool_gap

    def run(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Forecast the number of preschoolers in each subzone for the given forecast years,
        accounting for both existing residents and new BTO residents.

        Returns:
            A tuple of the existing preschools by subzone, the forecasted number
                of preschoolers, the forecasted number of preschools needed, and
                the gap between the number of preschools needed and the number of
                preschools available.
            existing_preschools_by_subzone: DataFrame of existing preschools by subzone.
            forecasted_num_preschoolers: DataFrame of forecasted preschoolers by subzone.
            forecasted_preschools_needed: DataFrame of forecasted preschools needed by subzone.
            preschool_gap: DataFrame of preschool supply/demand gap by subzone.
        """
        print("Running comprehensive preschool demand forecast...")

        # Get fertility data (both averaged for BTO and age-specific for existing residents)
        bto_birth_rates = self.fertility_processor.run(self.forecast_years)

        # Get age-specific fertility rates for existing residents
        self.fertility_processor.birth_years = (
            self.fertility_processor.birth_years_for_multiple_forecast_years(
                self.forecast_years
            )
        )
        self.fertility_processor.fertility_data = (
            self.fertility_processor.extrapolate_births(
                self.fertility_processor.birth_years
            )
        )
        fertility_rates_by_age = self.fertility_processor.fertility_data.loc[
            self.existing_residents_processor.all_mother_ages,
            [str(year) for year in self.fertility_processor.birth_years],
        ]

        # Get BTO and existing residents data
        bto_units_by_subzone = self.bto_processor.run(self.forecast_years)
        existing_women_by_age_bin = self.existing_residents_processor.run()

        # Calculate total preschoolers from both sources
        forecasted_num_preschoolers = self.calculate_preschoolers_all_years(
            bto_birth_rates,
            bto_units_by_subzone,
            fertility_rates_by_age,
            existing_women_by_age_bin,
        )

        # Calculate preschools needed
        forecasted_preschools_needed = (
            (forecasted_num_preschoolers / self.config.preschool_capacity)
            .round(0)
            .astype(int)
        )

        # Get existing preschools and calculate gap
        existing_preschools_by_subzone = self.preschool_processor.run()
        preschool_gap = self.calculate_preschool_gap(
            existing_preschools_by_subzone, forecasted_preschools_needed
        )

        return (
            existing_preschools_by_subzone,
            forecasted_num_preschoolers,
            forecasted_preschools_needed,
            preschool_gap,
        )


if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Run preschool demand forecasting")

    # Add arguments for each configurable parameter
    parser.add_argument(
        "--num_forecast_years",
        type=int,
        default=5,
        help="Number of years to forecast (default: 5)",
    )
    parser.add_argument(
        "--preschool_capacity",
        type=int,
        default=100,
        help="Capacity of each preschool (default: 100)",
    )
    parser.add_argument(
        "--min_preschool_age",
        type=int,
        default=18,
        help="Minimum preschool age in months (default: 18)",
    )
    parser.add_argument(
        "--max_preschool_age",
        type=int,
        default=72,
        help="Maximum preschool age in months (default: 72)",
    )
    parser.add_argument(
        "--fertility_data_path",
        type=str,
        default="data/BirthsAndFertilityRatesAnnual.csv",
        help="Path to fertility data CSV",
    )
    parser.add_argument(
        "--bto_data_path",
        type=str,
        default="data/btomapping.csv",
        help="Path to BTO mapping data CSV",
    )
    parser.add_argument(
        "--existing_residents_path",
        type=str,
        default="data/respopagesex2000to2020e.xlsx",
        help="Path to existing residents Excel file",
    )
    parser.add_argument(
        "--sheet_name",
        type=str,
        default="2020",
        help="Sheet name for existing residents data (default: 2020)",
    )
    parser.add_argument(
        "--header_row",
        type=int,
        default=2,
        help="Header row for existing residents data (default: 2)",
    )
    parser.add_argument(
        "--subzone_data_path",
        type=str,
        default="data/Master Plan 2019 Subzone Boundary (No Sea) (GEOJSON).geojson",
        help="Path to subzone data GeoJSON",
    )
    parser.add_argument(
        "--crs",
        type=str,
        default="urn:ogc:def:crs:OGC:1.3:CRS84",
        help="Coordinate reference system",
    )
    parser.add_argument(
        "--raw_preschool_data_path",
        type=str,
        default="data/ListingofCentres.csv",
        help="Path to preschool data CSV",
    )
    parser.add_argument(
        "--processed_preschool_data_path",
        type=str,
        default="data/preschools_data_processed.csv",
        help="Path to processed preschool data CSV",
    )

    # Parse arguments
    args = parser.parse_args()

    # Create config with CLI arguments
    forecaster_config = Config(
        num_forecast_years=args.num_forecast_years,
        preschool_capacity=args.preschool_capacity,
        min_preschool_age=args.min_preschool_age,
        max_preschool_age=args.max_preschool_age,
        fertility_data_path=Path(args.fertility_data_path),
        bto_data_path=Path(args.bto_data_path),
        existing_residents_path=Path(args.existing_residents_path),
        sheet_name=args.sheet_name,
        header_row=args.header_row,
        subzone_data_path=Path(args.subzone_data_path),
        crs=args.crs,
        raw_preschool_data_path=Path(args.raw_preschool_data_path),
        processed_preschool_data_path=Path(args.processed_preschool_data_path),
    )

    forecaster = Forecaster(forecaster_config)
    forecaster.run()
