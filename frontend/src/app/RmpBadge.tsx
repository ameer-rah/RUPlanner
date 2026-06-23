"use client";

import { useEffect, useState } from "react";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type RmpData = {
  name: string;
  rating: number | null;
  num_ratings: number;
  difficulty: number | null;
  would_take_again: number | null;
  legacy_id: number | null;
};

// Module-level caches so all badges for the same instructor share one fetch.
// _inFlight deduplicates concurrent requests; _done caches completed results.
const _inFlight = new Map<string, Promise<RmpData | null>>();
const _done = new Map<string, RmpData | null>();

function fetchRmp(name: string): Promise<RmpData | null> {
  const key = name.toLowerCase();
  if (_done.has(key)) return Promise.resolve(_done.get(key)!);
  if (_inFlight.has(key)) return _inFlight.get(key)!;
  const p = fetch(`${apiBase}/rmp/rating?name=${encodeURIComponent(name)}`)
    .then((r) => (r.ok ? r.json() : null))
    .catch(() => null)
    .then((data: RmpData | null) => {
      _done.set(key, data);
      _inFlight.delete(key);
      return data;
    });
  _inFlight.set(key, p);
  return p;
}

function ratingColor(r: number): string {
  if (r >= 4.0) return "#16a34a";
  if (r >= 3.0) return "#d97706";
  return "#dc2626";
}

export default function RmpBadge({ instructorName }: { instructorName: string }) {
  const [data, setData] = useState<RmpData | null | "loading">("loading");

  useEffect(() => {
    if (!instructorName || instructorName === "Staff") {
      setData(null);
      return;
    }
    fetchRmp(instructorName).then(setData);
  }, [instructorName]);

  if (data === "loading" || data === null || data.rating === null) return null;

  const url = data.legacy_id
    ? `https://www.ratemyprofessors.com/professor/${data.legacy_id}`
    : undefined;

  const badge = (
    <span
      title={`${data.name} · ${data.num_ratings} ratings · Difficulty: ${data.difficulty ?? "?"}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: 34,
        height: 34,
        borderRadius: "50%",
        background: ratingColor(data.rating),
        color: "#fff",
        fontWeight: 700,
        fontSize: 12,
        flexShrink: 0,
        cursor: url ? "pointer" : "default",
        textDecoration: "none",
      }}
    >
      {data.rating.toFixed(1)}
    </span>
  );

  if (url) {
    return (
      <a href={url} target="_blank" rel="noreferrer" style={{ textDecoration: "none" }}>
        {badge}
      </a>
    );
  }
  return badge;
}
