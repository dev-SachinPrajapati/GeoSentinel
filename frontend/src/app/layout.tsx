import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { Providers } from './providers';
import './globals.css';

const inter = Inter({ subsets: ['latin'], display: 'swap' });

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? 'https://yourdomain.com'),
  title: 'GeoSentinel | Disaster Monitor Real-Time Global Events',
  description: 'Live tracking of earthquakes, floods, and wildfires worldwide',
  keywords: ['disasters', 'earthquakes', 'floods', 'wildfires', 'real-time', 'map'],
  openGraph: {
    title: 'GeoSentinel | Real-Time Global Disaster Monitor',
    description: 'Live tracking of earthquakes, floods, wildfires, hurricanes and tsunamis worldwide.',
    url: 'https://yourdomain.com',
    siteName: 'GeoSentinel',
    images: [
      {
        url: '/logo.png',
        width: 512,
        height: 512,
        alt: 'GeoSentinel Logo',
      },
    ],
    type: 'website',
  },

  // Twitter / X card
  twitter: {
    card: 'summary',
    title: 'GeoSentinel | Real-Time Global Disaster Monitor',
    description: 'Live tracking of earthquakes, floods, wildfires, hurricanes and tsunamis.',
    images: ['/logo.png'],
  },

  // Favicon
  icons: {
    icon: '/logo.png',
    apple: '/logo.png',
  }
};


export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-gray-950 text-white antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
