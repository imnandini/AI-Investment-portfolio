export function researchUrl(symbol: string, name: string, exchange?: string) {
  const params = new URLSearchParams({ holding: symbol, name });
  if (exchange && exchange !== "UNKNOWN") params.set("exchange", exchange);
  return `/research?${params.toString()}`;
}

export function HoldingResearchLink({ symbol, name, exchange }: { symbol: string; name: string; exchange?: string }) {
  return <a className="button button-secondary" href={researchUrl(symbol, name, exchange)} aria-label={`Research ${name}`}>Research</a>;
}
