import pandas as pd
import matplotlib.pyplot as plt
from tabulate import tabulate

try:
    import seaborn as sns
    sns.set_palette("husl")
except ImportError:
    sns = None
    print("Seaborn not found. Visualizations will be less pretty.")

# Set style for plots
plt.style.use('dark_background')

def process_holdings(holdings):
    """Process raw holdings data into a DataFrame."""
    data = []
    for h in holdings:
        regular_qty = h['quantity'] + h['t1_quantity']
        mtf_qty = h.get('mtf', {}).get('quantity', 0) if isinstance(h.get('mtf'), dict) else 0
        total_qty = regular_qty + mtf_qty
        
        if total_qty != 0:
            regular_investment = regular_qty * h['average_price']
            mtf_investment = h.get('mtf', {}).get('value', 0) if isinstance(h.get('mtf'), dict) else 0
            total_investment = regular_investment + mtf_investment
            
            pnl_pct = (h['pnl'] / total_investment * 100) if total_investment > 0 else 0
            
            data.append({
                'Symbol': h['tradingsymbol'],
                'Exchange': h['exchange'],
                'Regular Qty': regular_qty,
                'MTF Qty': mtf_qty,
                'Total Qty': total_qty,
                'Avg Price': round(h['average_price'], 1),
                'Last Price': round(h['last_price'], 1),
                'Investment': round(total_investment, 0),
                'P&L': round(h['pnl'], 0),
                'P&L%': round(pnl_pct, 2),
                'Day Change': round(h['day_change'], 2),
                '% Change': round(h['day_change_percentage'], 2)
            })
    return pd.DataFrame(data)

def process_gtt_orders(gtt_orders):
    """Process raw GTT orders into a DataFrame."""
    data = []
    for order in gtt_orders:
        if order['status'] == 'active':
            condition = order['condition']
            orders = order['orders']
            
            trigger_values = condition['trigger_values']
            sl_trigger = trigger_values[0]
            tgt_trigger = trigger_values[1] if len(trigger_values) > 1 else 0
            
            data.append({
                'ID': order['id'],
                'Exchange': condition['exchange'],
                'Symbol': condition['tradingsymbol'],
                'SL Trigger Price': sl_trigger,
                'TGT Trigger Price': tgt_trigger,
                'Type': orders[0]['transaction_type'],
                'Qty': orders[0]['quantity'],
                'SL-Price': orders[0]['price'],
                'Status': order['status']
            })
    return pd.DataFrame(data)

def compare_positions(holdings_df, gtt_df):
    """Compare holdings with GTT orders and calculate risk metrics."""
    if holdings_df.empty:
        return pd.DataFrame()
        
    if gtt_df.empty:
        # Return holdings with empty risk metrics if no GTT orders
        common = holdings_df.copy()
        cols_to_add = ['SL Trigger Price', 'TGT Trigger Price', 'SL%', '% to TGT', 'RR Ratio', 'Open PNL Risk', 'Capital Risk']
        for col in cols_to_add:
            common[col] = 0
        return common

    merged = pd.merge(holdings_df, gtt_df, on='Symbol', how='left', suffixes=('', '_GTT'))
    
    # Filter for common stocks (those with GTT) for detailed risk analysis
    # or keep all to show missing GTTs
    common = merged.copy()
    
    # Calculate metrics where GTT exists
    mask = common['ID'].notna()
    
    common.loc[mask, 'SL%'] = ((common.loc[mask, 'Avg Price'] - common.loc[mask, 'SL Trigger Price']) / common.loc[mask, 'Avg Price'] * 100).round(2)
    common.loc[mask, '% to TGT'] = ((common.loc[mask, 'TGT Trigger Price'] - common.loc[mask, 'Last Price']) / common.loc[mask, 'Last Price'] * 100).round(2)
    
    common.loc[mask, 'Risk Per Share'] = common.loc[mask, 'Avg Price'] - common.loc[mask, 'SL Trigger Price']
    common.loc[mask, 'Reward Per Share'] = common.loc[mask, 'Last Price'] - common.loc[mask, 'Avg Price']
    
    # Handle division by zero for RR Ratio
    def calculate_rr(row):
        if pd.isna(row['ID']) or row['Risk Per Share'] == 0:
            return 0
        return round(row['Reward Per Share'] / row['Risk Per Share'], 2)

    common['RR Ratio'] = common.apply(calculate_rr, axis=1)
    
    common.loc[mask, 'Open PNL Risk'] = ((common.loc[mask, 'Last Price'] - common.loc[mask, 'SL Trigger Price']) * common.loc[mask, 'Total Qty']).round(2)
    common.loc[mask, 'Capital Risk'] = ((common.loc[mask, 'Avg Price'] - common.loc[mask, 'SL Trigger Price']) * common.loc[mask, 'Total Qty']).round(2)
    
    # Fill NaNs for non-GTT rows
    fill_cols = ['SL Trigger Price', 'TGT Trigger Price', 'SL%', '% to TGT', 'RR Ratio', 'Open PNL Risk', 'Capital Risk']
    common[fill_cols] = common[fill_cols].fillna(0)
    
    return common

def display_dashboard(kite):
    """Main function to fetch data and display the dashboard."""
    
    # 1. Fetch and Process Data
    print("Fetching holdings...")
    holdings = kite.holdings()
    holdings_df = process_holdings(holdings)
    
    print("Fetching GTT orders...")
    gtt_orders = kite.get_gtts()
    gtt_df = process_gtt_orders(gtt_orders)
    
    # 2. Display Tables
    print("\n" + "="*50)
    print("HOLDINGS SUMMARY")
    print("="*50)
    print(tabulate(holdings_df, headers='keys', tablefmt='fancy_grid', showindex=False))
    
    if not gtt_df.empty:
        print("\n" + "="*50)
        print("ACTIVE GTT ORDERS")
        print("="*50)
        print(tabulate(gtt_df, headers='keys', tablefmt='fancy_grid', showindex=False))
    
    # 3. Compare and Analyze
    detailed_analysis = compare_positions(holdings_df, gtt_df)
    
    # Filter for stocks with GTT for the risk table
    risk_table = detailed_analysis[detailed_analysis['ID'].notna()].copy()
    
    print("\n" + "="*50)
    print("RISK ANALYSIS (Stocks with GTT)")
    print("="*50)
    
    display_cols = [
        "Symbol", "Total Qty", "Avg Price", "Last Price", "Investment", 
        "SL Trigger Price", "TGT Trigger Price", "P&L", "P&L%", 
        "SL%", "% to TGT", "RR Ratio", "Open PNL Risk", "Capital Risk"
    ]
    
    if not risk_table.empty:
        print(tabulate(risk_table[display_cols], headers='keys', tablefmt='fancy_grid', showindex=False))
        
        # Summary Metrics
        total_open_risk = risk_table['Open PNL Risk'].sum()
        total_capital_risk = risk_table['Capital Risk'].sum()
        total_open_profit = risk_table['P&L'].sum()
        
        print(f"\nTotal Open PNL Risk: ₹{total_open_risk:,.0f}")
        print(f"Total Capital Risk:  ₹{total_capital_risk:,.0f}")
        print(f"Total Open Profit:   ₹{total_open_profit:,.0f}")
        
    # 4. Holdings without GTT
    no_gtt = detailed_analysis[detailed_analysis['ID'].isna()]
    if not no_gtt.empty:
        print("\n" + "="*50)
        print(f"HOLDINGS WITHOUT GTT ORDERS ({len(no_gtt)} stocks)")
        print("="*50)
        print(tabulate(no_gtt[holdings_df.columns], headers='keys', tablefmt='fancy_grid', showindex=False))
        print(f"\nTotal P&L (No GTT): ₹{no_gtt['P&L'].sum():,.0f}")
    else:
        print("\n✓ All holdings have GTT orders configured!")
        
    # 5. Visualizations
    if not holdings_df.empty:
        # Portfolio Allocation
        plt.figure(figsize=(10, 6))
        plt.pie(holdings_df['Investment'], labels=holdings_df['Symbol'], autopct='%1.1f%%', startangle=140)
        plt.title('Portfolio Allocation by Investment')
        plt.show()
        
        # P&L Bar Chart
        plt.figure(figsize=(12, 6))
        colors = ['green' if x > 0 else 'red' for x in holdings_df['P&L']]
        
        if sns:
            sns.barplot(x='Symbol', y='P&L', data=holdings_df, palette=colors)
        else:
            plt.bar(holdings_df['Symbol'], holdings_df['P&L'], color=colors)
            
        plt.title('Profit & Loss by Stock')
        plt.xticks(rotation=45)
        plt.ylabel('P&L (₹)')
        plt.show()
        
    if not risk_table.empty:
        # Risk vs Reward Scatter
        plt.figure(figsize=(10, 6))
        
        if sns:
            sns.scatterplot(data=risk_table, x='Capital Risk', y='P&L', size='Investment', hue='Symbol', sizes=(100, 1000), legend=False)
        else:
            plt.scatter(risk_table['Capital Risk'], risk_table['P&L'], s=risk_table['Investment']/100, alpha=0.5)
            
        # Add labels
        for i in range(risk_table.shape[0]):
            plt.text(
                risk_table['Capital Risk'].iloc[i], 
                risk_table['P&L'].iloc[i], 
                risk_table['Symbol'].iloc[i],
                horizontalalignment='left', 
                size='medium', 
                color='white', 
                weight='semibold'
            )
            
        plt.title('Risk vs Reward (Bubble Size = Investment)')
        plt.xlabel('Capital Risk (₹)')
        plt.ylabel('Current P&L (₹)')
        plt.axhline(0, color='white', linestyle='--', alpha=0.5)
        plt.axvline(0, color='white', linestyle='--', alpha=0.5)
        plt.grid(True, alpha=0.2)
        plt.show()
