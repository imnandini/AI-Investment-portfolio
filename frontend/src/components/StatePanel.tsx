import type { ReactNode } from "react";
import { ArrowRight, Inbox } from "lucide-react";
import { Link } from "react-router-dom";

export function StatePanel({ title, description, action, to, icon = <Inbox size={19} /> }: {
  title: string; description: string; action?: string; to?: string; icon?: ReactNode;
}) {
  return <section className="state-panel"><span className="state-icon">{icon}</span><h3>{title}</h3><p>{description}</p>{action && to && <Link className="text-link" to={to}>{action}<ArrowRight size={15} /></Link>}</section>;
}
