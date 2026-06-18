import './style.css';
export const metadata = { title: 'Alpha Radar AI', description: 'AI stock radar dashboard' };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="ko"><body>{children}</body></html>;
}
