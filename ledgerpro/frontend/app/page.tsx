import React from 'react';

// Define a type for common icon props to ensure consistency
type IconProps = {
  className?: string;
  size?: number;
  color?: string;
};

// Example Custom Icons (replace with actual SVG paths or components)
const HomeIcon: React.FC<IconProps> = ({ className, size = 24, color = "currentColor" }) => (
  <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
    <polyline points="9 22 9 12 15 12 15 22"></polyline>
  </svg>
);

const TransactionsIcon: React.FC<IconProps> = ({ className, size = 24, color = "currentColor" }) => (
  <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="1" x2="12" y2="23"></line>
    <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
  </svg>
);

const ReportsIcon: React.FC<IconProps> = ({ className, size = 24, color = "currentColor" }) => (
  <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
    <line x1="12" y1="11" x2="12" y2="17"></line>
    <line x1="9" y1="14" x2="15" y2="14"></line>
  </svg>
);

const SettingsIcon: React.FC<IconProps> = ({ className, size = 24, color = "currentColor" }) => (
  <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3"></circle>
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
  </svg>
);


export default function HomePage() {
  return (
    <div style={styles.appContainer}>
      <aside style={styles.sidebar}>
        <div style={styles.sidebarHeader}>
          <h1 style={styles.logo}>LedgerPro</h1>
        </div>
        <nav style={styles.nav}>
          <a href="#" style={{ ...styles.navLink, ...styles.navLinkActive }}>
            <HomeIcon className="nav-icon" /> Dashboard
          </a>
          <a href="#" style={styles.navLink}>
            <TransactionsIcon className="nav-icon" /> Transactions
          </a>
          <a href="#" style={styles.navLink}>
            <ReportsIcon className="nav-icon" /> Reports
          </a>
          <a href="#" style={styles.navLink}>
            <SettingsIcon className="nav-icon" /> Settings
          </a>
        </nav>
      </aside>

      <main style={styles.mainContent}>
        <header style={styles.header}>
          <h2>Dashboard Overview</h2>
          <div style={styles.headerActions}>
            <button className="btn btn-primary" style={styles.actionButton}>New Transaction</button>
            <input type="search" placeholder="Search..." className="form-control" style={styles.searchInput} />
          </div>
        </header>

        <section style={styles.contentGrid}>
          <div style={{ ...styles.card, ...styles.neumorphicCard }}>
            <h3>Account Balance</h3>
            <p style={styles.balanceAmount}>$12,345.67</p>
            <button className="btn btn-secondary btn-sm">View Details</button>
          </div>
          <div style={{ ...styles.card, ...styles.neumorphicCard }}>
            <h3>Recent Activity</h3>
            <ul style={styles.activityList}>
              <li>Payment to Supplier X - $250.00</li>
              <li>Invoice #1023 Paid - $1,200.00</li>
              <li>Office Supplies - $75.50</li>
            </ul>
            <a href="#" className="link-primary">View All</a>
          </div>
          <div style={{ ...styles.card, ...styles.glassmorphicCard, gridColumn: 'span 2' }}>
            <h3>Spending Overview (Glassmorphism Example)</h3>
            {/* Placeholder for a chart */}
            <div style={styles.chartPlaceholder}>Chart Area</div>
            <p>This card demonstrates a glassmorphic effect.</p>
          </div>
           <div style={{ ...styles.card, ...styles.neumorphicCard, gridColumn: 'span 2' }}>
            <h3>Income vs Expenses (Neumorphism Example)</h3>
            {/* Placeholder for a chart */}
            <div style={styles.chartPlaceholder}>Chart Area</div>
             <p>This card demonstrates a neumorphic effect.</p>
          </div>
        </section>

        <footer style={styles.footer}>
          <p>&copy; {new Date().getFullYear()} LedgerPro. All rights reserved.</p>
        </footer>
      </main>
      {/* Global styles for icons that might be missed by CSS modules or specific component styling */}
      <style jsx global>{`
        .nav-icon {
          margin-right: 10px;
          vertical-align: middle;
        }
      `}</style>
    </div>
  );
}

const styles: { [key: string]: React.CSSProperties } = {
  appContainer: {
    display: 'flex',
    minHeight: '100vh',
    backgroundColor: 'var(--background-color)', // Use global CSS variable
  },
  sidebar: {
    width: '250px',
    backgroundColor: '#f8f9fa', // A very light gray, almost white, for the sidebar
    padding: '20px',
    borderRight: '1px solid #dee2e6', // Light border
    display: 'flex',
    flexDirection: 'column',
  },
  sidebarHeader: {
    marginBottom: '30px',
    textAlign: 'center',
  },
  logo: {
    fontSize: '2rem', // Larger logo
    fontWeight: 'bold',
    color: 'var(--primary-color)', // Use global CSS variable
  },
  nav: {
    display: 'flex',
    flexDirection: 'column',
  },
  navLink: {
    color: 'var(--text-color)', // Use global CSS variable
    padding: '12px 15px',
    marginBottom: '8px',
    borderRadius: '6px',
    textDecoration: 'none',
    display: 'flex',
    alignItems: 'center',
    fontSize: '1rem',
    transition: 'background-color 0.2s ease, color 0.2s ease',
  },
  navLinkActive: { // Added this style for active link indication
    backgroundColor: 'rgba(0, 123, 255, 0.1)', // Light primary color background
    color: 'var(--primary-color)',
    fontWeight: '500',
  },
  mainContent: {
    flex: 1,
    padding: '30px',
    display: 'flex',
    flexDirection: 'column',
    overflowY: 'auto', // Allow scrolling for main content
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '30px',
    paddingBottom: '20px',
    borderBottom: '1px solid #eee' // Subtle separator for header
  },
  headerActions: {
    display: 'flex',
    alignItems: 'center',
  },
  actionButton: {
    marginRight: '15px',
  },
  searchInput: {
    minWidth: '250px', // Give search input a decent width
  },
  contentGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', // Responsive grid
    gap: '25px', // Space between cards
    flex: 1, // Allow grid to take available space
  },
  card: {
    padding: '25px',
    borderRadius: '12px', // Softer corners
    backgroundColor: 'var(--background-color)', // Card background
  },
  neumorphicCard: {
    backgroundColor: '#e0e5ec', // Light background for neumorphism
    boxShadow: '9px 9px 16px #a3b1c6, -9px -9px 16px #ffffff', // Neumorphic shadows
    border: '1px solid rgba(255, 255, 255, 0.3)', // Subtle border to enhance the effect
  },
  glassmorphicCard: {
    backgroundColor: 'rgba(255, 255, 255, 0.3)', // Semi-transparent background
    backdropFilter: 'blur(10px)', // Blur effect for the background
    border: '1px solid rgba(255, 255, 255, 0.18)', // Subtle border
    boxShadow: '0 8px 32px 0 rgba(31, 38, 135, 0.37)', // Soft shadow
    color: '#333', // Ensure text is readable on glass
  },
  balanceAmount: {
    fontSize: '2.5rem',
    fontWeight: 'bold',
    color: 'var(--primary-color)',
    margin: '10px 0 20px 0',
  },
  activityList: {
    listStyle: 'none',
    padding: 0,
    margin: '10px 0',
  },
  chartPlaceholder: {
    height: '150px',
    backgroundColor: '#e9ecef', // Light placeholder color
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: '8px',
    marginBottom: '15px',
    color: '#6c757d'
  },
  footer: {
    marginTop: 'auto', // Push footer to the bottom
    padding: '20px 0',
    textAlign: 'center',
    borderTop: '1px solid #eee', // Subtle separator for footer
    fontSize: '0.9rem',
    color: 'var(--secondary-color)',
  },
};
