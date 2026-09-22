# Planetary Surveyor v1.1.1 Public Beta

I finally found why some players could see the settings menu while F10 did
nothing. The Python loader was sometimes looking for `app\mod` inside
`GAMEDATA`. Version 1.1.1 fixes that.

Do not copy `app` or `runtime` into `GAMEDATA`. Install the archive into the main
No Man's Sky folder as usual. Python is already included.

Fauna scanning is the reliable part. Flora and minerals are still experimental
and can miss a few entries on some planets.
