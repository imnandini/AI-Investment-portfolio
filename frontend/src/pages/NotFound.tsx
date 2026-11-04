import { Link } from "react-router-dom";

export function NotFoundPage() {
  return <main className="not-found"><span className="section-kicker">PAGE NOT FOUND</span><h1>This page is off the map.</h1><p>That address does not match a workspace page.</p><Link className="button button-primary" to="/">Back to overview</Link></main>;
}
