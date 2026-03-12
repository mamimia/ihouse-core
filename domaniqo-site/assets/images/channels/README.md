# Channel Logos

Place logo files here to replace the text-based placeholders.

## File names expected:

1. airbnb.svg
2. booking-com.svg
3. expedia.svg
4. vrbo.svg
5. agoda.svg
6. traveloka.svg
7. trip-com.svg
8. rakuten.svg
9. despegar.svg
10. klook.svg
11. makemytrip.svg
12. google-vr.svg
13. hostelworld.svg
14. hotelbeds.svg

## Requirements:

- Format: SVG preferred, PNG also works
- Color: White or light-colored on transparent background
- The CSS applies `grayscale(100%) brightness(2)` filter, so light logos work best
- Max display size: 80px wide × 28px tall
- Keep file sizes small (under 10KB each)

## How to activate:

In `index.html`, find the channels section and replace:
```html
<div class="ch-item"><span>Airbnb</span></div>
```
with:
```html
<div class="ch-item"><img src="assets/images/channels/airbnb.svg" alt="Airbnb"></div>
```

Repeat for each channel.
