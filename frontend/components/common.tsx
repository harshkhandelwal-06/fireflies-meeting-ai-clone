import type { ReactNode, ComponentType } from 'react';
import { ChevronRight, Clock3, FileText, type LucideIcon } from 'lucide-react';

export type MeetingCardData = {
  id: number;
  title: string;
  date: string;
  duration: number;
  participants: string[];
  topics?: string[];
};

const dateFmt = (d: string) =>
  new Date(d).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });

type IconComponent = LucideIcon;

export function AssistantCard({
  icon: Icon,
  title,
  sub,
  onClick,
}: {
  icon: IconComponent;
  title: string;
  sub: string;
  onClick: () => void;
}) {
  return (
    <button className="assistant-tile" onClick={onClick}>
      <div className="icon-tile"><Icon size={19} /></div>
      <b>{title}</b>
      <span>{sub}</span>
    </button>
  );
}

export function MeetingCard({ m, onClick }: { m: MeetingCardData; onClick: () => void }) {
  return (
    <button onClick={onClick} className="meeting-card">
      <div className="meeting-icon"><FileText size={17} /></div>
      <div className="meeting-main">
        <b>{m.title}</b>
        <span>
          {dateFmt(m.date)} · {m.participants.slice(0, 3).join(', ')}
          {m.participants.length > 3 ? ' + more' : ''}
        </span>
        <div className="chips">{m.topics?.slice(0, 2).map(t => <span key={t}>{t}</span>)}</div>
      </div>
      <span className="meeting-duration"><Clock3 size={13} />{m.duration}m</span>
      <ChevronRight size={15} />
    </button>
  );
}

export function Info({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="info-block">
      <b>{title}</b>
      <ul>{items?.length ? items.map(x => <li key={x}>{x}</li>) : <li>Nothing captured yet.</li>}</ul>
    </div>
  );
}

export function Metric({ title, value, sub }: { title: string; value: string; sub: string }) {
  return <div className="metric"><span>{title}</span><b>{value}</b><small>{sub}</small></div>;
}

export function SettingRow({
  icon: Icon,
  title,
  sub,
  children,
}: {
  icon: IconComponent;
  title: string;
  sub: string;
  children?: ReactNode;
}) {
  return (
    <div className="setting-row">
      <Icon size={20} />
      <div><b>{title}</b><span>{sub}</span></div>
      <div className="setting-control">{children}</div>
    </div>
  );
}
