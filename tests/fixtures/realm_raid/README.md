# Realm raid recognition fixtures

`positive_composite.png` is a deterministic wiring fixture. It places each
720p template at a known position inside that node's configured ROI.

`battle_negative.png` is the old script's real `screen.png` captured during a
battle, resized from 1920x1080 with `cv2.INTER_AREA`. The former full-screen,
grayscale `End.png` check scores about 0.609 against this frame, so the old 0.60
threshold could click during combat. The new reward node uses a bounded ROI and
a 0.72 threshold, and this image is a required negative regression sample.
