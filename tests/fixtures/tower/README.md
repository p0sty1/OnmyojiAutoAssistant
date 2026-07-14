# Tower recognition fixtures

`positive_composite.png` is a deterministic synthetic fixture. It proves that
the scaled templates, configured ROIs, thresholds, and template paths agree; it
is not a substitute for a real tower screenshot.

`negative_non_tower.png` is a real 1920x1080 game screenshot scaled to
1280x720 with `cv2.INTER_AREA`. None of the four tower states is present, so it
acts as a false-positive regression sample.

The original source directory did not contain real positive screenshots for
the four tower states. Live-device validation is still required before release.
