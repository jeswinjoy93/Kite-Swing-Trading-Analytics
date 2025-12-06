import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
try:
    import seaborn as sns
except ImportError:
    sns = None
    print("Seaborn not found. Visualizations will be less pretty.")
import numpy as np
try:
    import ipywidgets as widgets
    from IPython.display import display, clear_output
except ImportError:
    widgets = None
    print("ipywidgets not found. Interactive features will be disabled.")

# Set style
plt.style.use('dark_background')

def fetch_data(tickers, benchmark='^NSEI', period='1y', interval='1wk'):
    """
    Fetch historical data for tickers and benchmark from yfinance.
    """
    all_tickers = tickers + [benchmark]
    print(f"Fetching data for: {all_tickers} (Interval: {interval})")
    data = yf.download(all_tickers, period=period, interval=interval)['Close']
    
    # Handle cases where data might be missing or columns are MultiIndex
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
        
    return data.dropna()

def calculate_rrg(data, benchmark='^NSEI', window=14):
    """
    Calculate RRG metrics: RS-Ratio and RS-Momentum.
    """
    rrg_data = pd.DataFrame(index=data.index)
    
    # Benchmark series
    bm_series = data[benchmark]
    
    results = {}
    
    for ticker in data.columns:
        if ticker == benchmark:
            continue
            
        # 1. Relative Strength
        rs = data[ticker] / bm_series
        
        # 2. RS-Ratio (Trend)
        # Using a simple moving average for the ratio
        rs_ratio = 100 * (rs / rs.rolling(window=window).mean())
        
        # 3. RS-Momentum (Rate of Change of the Trend)
        # Using the ratio relative to its own moving average to normalize momentum around 100
        rs_momentum = 100 * (rs_ratio / rs_ratio.rolling(window=window).mean())
        
        results[ticker] = pd.DataFrame({
            'RS_Ratio': rs_ratio,
            'RS_Momentum': rs_momentum
        })
        
    return results

def plot_rrg(rrg_results, tail_length=10, interval='Weekly'):
    """
    Plot the RRG chart with tails.
    """
    plt.figure(figsize=(12, 10))
    
    # Draw Quadrants
    plt.axhline(100, color='white', linestyle='--', alpha=0.5)
    plt.axvline(100, color='white', linestyle='--', alpha=0.5)
    
    # Quadrant Labels
    plt.text(102, 102, "LEADING", color='green', fontsize=12, fontweight='bold', alpha=0.7)
    plt.text(98, 102, "IMPROVING", color='blue', fontsize=12, fontweight='bold', alpha=0.7, ha='right')
    plt.text(98, 98, "LAGGING", color='red', fontsize=12, fontweight='bold', alpha=0.7, ha='right', va='top')
    plt.text(102, 98, "WEAKENING", color='orange', fontsize=12, fontweight='bold', alpha=0.7, va='top')
    
    if sns:
        colors = sns.color_palette("hsv", len(rrg_results))
    else:
        # Fallback to matplotlib colormap
        cmap = plt.get_cmap('hsv')
        colors = [cmap(i) for i in np.linspace(0, 1, len(rrg_results))]
    
    for i, (ticker, df) in enumerate(rrg_results.items()):
        # Get the last 'tail_length' points
        tail = df.iloc[-tail_length:]
        
        if tail.empty or tail['RS_Ratio'].isna().all():
            continue
            
        # Plot the tail
        plt.plot(tail['RS_Ratio'], tail['RS_Momentum'], color=colors[i], alpha=0.6, linewidth=2)
        
        # Plot the head (current position)
        current = tail.iloc[-1]
        plt.scatter(current['RS_Ratio'], current['RS_Momentum'], color=colors[i], s=100, label=ticker, edgecolors='white')
        
        # Add label
        plt.text(current['RS_Ratio'], current['RS_Momentum'], f"  {ticker}", color=colors[i], fontsize=9, fontweight='bold')
        
        # Add arrow to show direction
        if len(tail) > 1:
            prev = tail.iloc[-2]
            plt.arrow(prev['RS_Ratio'], prev['RS_Momentum'], 
                      current['RS_Ratio'] - prev['RS_Ratio'], 
                      current['RS_Momentum'] - prev['RS_Momentum'], 
                      color=colors[i], head_width=0.2, alpha=0.8)

    plt.title(f"Relative Rotation Graph ({interval})", fontsize=16)
    plt.xlabel("RS-Ratio (Trend)", fontsize=12)
    plt.ylabel("RS-Momentum (Momentum)", fontsize=12)
    plt.grid(True, alpha=0.2)
    plt.tight_layout()
    plt.show()

def generate_sector_rrg(interval='1wk'):
    """
    Convenience function to generate RRG for major Indian sectors.
    Args:
        interval (str): '1d' for Daily, '1wk' for Weekly. Default is '1wk'.
    """
    # Major Indian Sector Indices (Yahoo Finance Tickers)
    # Note: Yahoo Finance tickers for NSE indices often start with ^
    sectors = [
        '^NSEBANK',    # Nifty Bank
        '^CNXIT',      # Nifty IT
        '^CNXAUTO',    # Nifty Auto
        '^CNXMETAL',   # Nifty Metal
        '^CNXFMCG',    # Nifty FMCG
        '^CNXPHARMA',  # Nifty Pharma
        '^CNXREALTY',  # Nifty Realty
        '^CNXENERGY',  # Nifty Energy
        '^CNXINFRA'    # Nifty Infra
    ]
    
    benchmark = '^NSEI' # Nifty 50
    
    try:
        data = fetch_data(sectors, benchmark, interval=interval)
        rrg_results = calculate_rrg(data, benchmark)
        
        label = "Weekly" if interval == '1wk' else "Daily"
        plot_rrg(rrg_results, interval=label)
    except Exception as e:
        print(f"Error generating RRG: {e}")
        print("Please ensure yfinance is installed and you have internet access.")

def interactive_rrg():
    """
    Displays an interactive RRG chart with a toggle for Weekly/Daily interval.
    """
    if widgets is None:
        print("ipywidgets is not installed. Please install it to use this feature.")
        return

    # Create Toggle Buttons
    interval_toggle = widgets.ToggleButtons(
        options=[('Weekly', '1wk'), ('Daily', '1d')],
        description='Interval:',
        disabled=False,
        button_style='', # 'success', 'info', 'warning', 'danger' or ''
        tooltips=['Weekly RRG', 'Daily RRG'],
    )
    
    output = widgets.Output()
    
    def on_value_change(change):
        with output:
            clear_output(wait=True)
            generate_sector_rrg(interval=change['new'])
            
    interval_toggle.observe(on_value_change, names='value')
    
    # Display widgets
    display(interval_toggle, output)
    
    # Trigger initial display
    with output:
        generate_sector_rrg(interval=interval_toggle.value)

if __name__ == "__main__":
    interactive_rrg() # Uncomment to test interactive mode in notebook
    # generate_sector_rrg()
