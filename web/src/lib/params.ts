// Yol parametrelerini anlık görüntü kayıtlarına çevirir. `dynamicParams = false` olduğu
// için derlenmemiş yol zaten 404'tür; burada bulunamayan kayıt bir derleme hatasıdır.
import { notFound } from "next/navigation";
import { isLang, type Lang } from "../../site.config.ts";
import type { League, Match, Snapshot, Team } from "./snapshot-types.ts";

export function langOf(value: string): Lang {
  if (!isLang(value)) notFound();
  return value;
}

export function leagueOf(snapshot: Snapshot, slug: string): League {
  return snapshot.leagues.find((league) => league.slug === slug) ?? notFound();
}

export function teamOf(snapshot: Snapshot, league: League, slug: string): Team {
  const team = snapshot.teams.find((each) => each.league_id === league.id && each.slug === slug);
  return team ?? notFound();
}

export function matchOf(snapshot: Snapshot, league: League, pathId: string, slug: string): Match {
  const match = snapshot.matches.find(
    (each) => each.league_id === league.id && each.path_id === pathId && each.slug === slug,
  );
  return match ?? notFound();
}
