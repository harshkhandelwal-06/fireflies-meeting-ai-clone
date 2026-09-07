import './globals.css';
import type { ReactNode } from 'react';
export const metadata={title:'Fireflies Clone',description:'AI meeting memory, transcription and meeting intelligence'};
export default function RootLayout({children}:{children:ReactNode}){return <html lang="en"><body>{children}</body></html>}
