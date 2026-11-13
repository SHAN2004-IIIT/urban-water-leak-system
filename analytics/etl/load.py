"""Write derived outputs, leaving the original CSV files untouched."""
from pathlib import Path

def export(df, output, name):
    df.to_csv(output / name, index=False, na_rep='')
    print(f'OUTPUT   {name}: {len(df):,} rows')

