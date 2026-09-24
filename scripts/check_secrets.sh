#!/usr/bin/env bash
# İzlenen hiçbir dosyada gerçek secret olmamalı; .env ignore edilmiş olmalı.
#
# Depo PUBLIC. `.env` canlı bir API anahtarı ve veritabanı parolası tutuyor. Bir
# secret commit'e kaçarsa insan kontrol noktası olmadan anında halka açılır ve
# geri alınamaz: push'lanmış bir anahtar artık yanmıştır, silmek yetmez, döndürülür.
set -uo pipefail

fail=0

if ! git check-ignore -q .env 2>/dev/null; then
  echo "HATA: .env gitignore'da değil"
  fail=1
fi

if git ls-files --error-unmatch .env >/dev/null 2>&1; then
  echo "HATA: .env git tarafından izleniyor"
  fail=1
fi

# Dolu değer atanmış secret benzeri satırlar (boş .env.example şablonu hariç). `SITE_DATABASE_URL`
# `DATABASE_URL` alt dizesiyle yakalanır; Netlify kişisel erişim tokenı hesabın bütün sitelerine
# yetkilidir (AK18) — adıyla listededir.
git grep -nIE '(ODDS_API_KEY|DATABASE_URL|SUPABASE_[A-Z_]*KEY|TYPESAFE_API_KEY|NETLIFY_AUTH_TOKEN)[[:space:]]*=[[:space:]]*.?[A-Za-z0-9+/:@._-]{12,}' \
  -- . ':!*.md' ':!.env.example' ':!uv.lock'
found=$?

# 0 = eşleşme var, 1 = temiz, ≥2 = git'in KENDİSİ düştü (bozuk pathspec, repo yok).
# Üçüncüsü `if git grep ...` kalıbında "temiz" sayılır: tarama sessizce kapanır ve
# kapı sonsuza dek yeşil kalır. Atlanan kontrol geçmek değildir — adıyla kırmızı.
case "$found" in
  0)
    echo "HATA: izlenen dosyada dolu secret ataması var"
    fail=1
    ;;
  1) ;;
  *)
    echo "HATA: git grep taraması koşamadı (exit $found) — tarama yapılmadı"
    fail=1
    ;;
esac

# Netlify kişisel erişim tokenı biçimiyle de aranır: ad=değer taraması YAML/JSON değerini,
# `--auth` bayrağını, adsız tokenı, küçük harfli adı ve Markdown'ı görmez (T8 incelemesi I4).
# `nfp_` + 36 alfasayısal yanlış alarm vermez (depoda 0 eşleşme ölçüldü) — `.md` DÂHİL.
git grep -nIE 'nfp_[A-Za-z0-9]{36}' -- . ':!uv.lock'
token=$?

case "$token" in
  0)
    echo "HATA: izlenen dosyada Netlify erişim tokenı var"
    fail=1
    ;;
  1) ;;
  *)
    echo "HATA: Netlify token taraması koşamadı (exit $token) — tarama yapılmadı"
    fail=1
    ;;
esac

[ "$fail" -eq 0 ] && echo "secret taraması temiz"
exit "$fail"
