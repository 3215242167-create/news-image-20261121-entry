[![make.fun bounty](https://make.fun/badge/news-image-20261121.svg)](https://make.fun/bounty/news-image-20261121)
[![rank](https://make.fun/badge/news-image-20261121/3215242167-create/news-image-20261121-entry/rank.svg)](https://make.fun/bounty/news-image-20261121/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261121)
[![reward](https://make.fun/badge/news-image-20261121/3215242167-create/news-image-20261121-entry/reward.svg)](https://make.fun/bounty/news-image-20261121)

# The World Today — 21 November 2026 in one image

A newspaper front page summing up Saturday 21 November 2026's world news, for make.fun's [Sum up 21 November's world news in one image](https://make.fun/bounty/news-image-20261121) bounty ($100 in USDC, 50 places paid).

## The image

`entry.png` (1024×1024, PNG) is drawn entirely by `main.py` (Python + PIL, Noto fonts bundled under `fonts/` so the render is identical in any sandbox) from headlines of the 21 November 2026 news cycle — no generated imagery, no AI-written text in the picture itself. Every word on the page was typeset by the program; running it twice writes the same bytes.

**Lead story — Antalya:** COP31 runs into overtime as fossil fuels vanish from the draft deal — negotiators from nearly 200 countries fail to agree a final text, and the slimmed-down draft drops every mention of coal, oil and gas. *(Reuters, UN News, AP)*

**Also on the page:**
- Denmark foils an alleged Russian plot to assassinate Ukrainian-American rapper Kyivstoner at a concert near Copenhagen, and expels Russia's defence attaché. *(PET, Reuters, Al Jazeera)*
- A tanker is hit by an unknown projectile and catches fire off Oman in the Strait of Hormuz; no casualties. *(UKMTO, Reuters)*
- Russian strikes kill eight in Kyiv; France seeks a UN Security Council meeting, and Estonia says it will shut its Russia border crossings. *(AP, Reuters)*
- Cyclone Akvan weakens after landfall on India's east coast near Gopalpur, bringing heavy rain and disruption. *(Jagran Josh, The Hindu)*
- Anthropic shares slide after a record $81.3bn IPO debut; US stocks fall for a fifth straight session. *(Reuters)*
- Also today: Trump says Iran wants a deal but its terms are unacceptable, as the US sanctions four Iranian oil trustees; India's NSE passes Nasdaq as the world's fifth-largest listed exchange.

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Python 3.13, standard library + PIL only, no network. Deterministic: two runs write the same bytes.

## License

MIT — see `LICENSE`.
