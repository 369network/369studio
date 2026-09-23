# -*- coding: utf-8 -*-
"""Santan prompt builder v2 — Seedance Film Director standard.
Key changes vs v1: no face/skin description when a sheet is attached; no "cinematic";
per-ref do-not-copy clause; timestamped beats; screen-side lock; positive-first audio
with background-voice exclusion; explicit ENDING STATE (feeds our last-frame chain)."""
import json, os
P = "projects/santan"
os.makedirs(f"{P}/docs", exist_ok=True)

LOOK = ("Location documentary capture of an Indian television family drama. Real room light with two colour "
        "temperatures — a warm practical against cooler ambient. Faint haze between lens and subject. Coarse "
        "visible grain, soft corners, slight vignetting, motion blur on anything that moves; highlights clip "
        "where they are brightest and shadows sit heavy. Skin renders with real texture and natural specular "
        "sheen where light genuinely catches it, matte elsewhere, never smoothed, never waxy. Nothing is "
        "perfectly sharp, perfectly exposed or perfectly composed.")

# identity refs: NO facial features, NO skin tone — the plate carries them.
ROLE = {
 "suman":   "SUMAN, the wife",
 "aakash":  "AAKASH, the husband",
 "naina":   "NAINA, the young woman",
 "saas":    "SAAS, AAKASH's elderly mother",
 "mausi":   "MAUSI, the frail elderly woman",
 "kamla":   "KAMLA, SUMAN's elderly mother",
}
LOC = {
 "ghar_night":"Interior living room of a middle-class Indian home at night. A warm ceiling bulb is the only practical; the window behind the sofa is cooler and darker. Beige walls, a wooden sofa with maroon cushions, a framed wedding photograph, drawn curtains.",
 "ghar_night_door":"The same living room at night, the front door now standing open on a dark street; the warm interior bulb against the cold blue outside.",
 "ghar_ext":"A quiet dark residential street outside the home, one distant streetlamp, a car with red tail-lights pulling away, and behind it the warm lit rectangle of the open doorway.",
 "ghar_lamp":"The same living room later the same night, the ceiling bulb off and a single warm table lamp left on; most of the room sits in deep shadow.",
 "maike":"Interior of a modest older woman's home in the evening. A warm bulb overhead, a small lit diya on a shelf of framed deity pictures, pale green walls, a simple two-seater sofa, a tulsi plant visible through an open doorway.",
 "maike_window":"The same modest home at night, at a window; the room lit only by a weak warm bulb behind and cold street light through the glass.",
}

# scene: chars, loc, chain_from, sides, start, beats[3], camera, lines[(speaker,hindi)], ending
S = {}
def add(i, chars, loc, ch, start, beats, camera, lines, ending, sides=""):
    S[i] = dict(chars=chars, loc=loc, chain_from=ch, start=start, beats=beats,
                camera=camera, lines=lines, ending=ending, sides=sides)

add(1, ["suman","aakash","naina"], "ghar_night", None,
 "The front door is shut. AAKASH stands near the sofa; NAINA stands a little behind and to his right, hands at her sides. The room is still.",
 ["The front door swings open and SUMAN steps in from the dark; she stops dead two paces inside, one hand still on the door.",
  "Her breathing goes shallow and her right arm comes up, finger extended toward AAKASH, while AAKASH straightens and half-rises from where he stood.",
  "She speaks; NAINA takes a half-step backwards behind AAKASH's shoulder and stops there."],
 "Starts on a push-in through the open doorway behind SUMAN, then settles into a wide that holds SUMAN in the left third and AAKASH and NAINA in the right third. The camera does not move again once she begins to speak.",
 [("SUMAN","बस करो आकाश! अब और झूठ मत बोलना... इस लड़की को मैंने अपने ही घर में, अपने ही पति के साथ देखा है!")],
 "SUMAN stands just inside the door, left third of frame, arm still raised and finger still pointing. AAKASH is half-risen in the right third, NAINA behind his right shoulder. The door behind SUMAN is open on darkness.",
 "SUMAN holds screen-left and AAKASH screen-right for the entire runtime; they never swap sides and the camera never crosses between them.")

add(2, ["suman","aakash","naina"], "ghar_night", 1,
 "SUMAN stands inside the door, arm still raised. AAKASH is half-risen by the sofa, NAINA behind his right shoulder.",
 ["AAKASH finishes rising and brings both palms up, open, at chest height.",
  "He takes one slow step toward SUMAN and stops; SUMAN's arm comes down and folds across her chest, jaw set.",
  "He speaks with his hands still open; she does not move, and her eyes do not leave his face."],
 "Reverse angle onto AAKASH in the right third, slow dolly-in that begins only when he raises his palms. SUMAN stays soft in the left foreground, back three-quarters to camera. The camera never crosses between them.",
 [("AAKASH","सुमन, सुनो तो सही... ये वो नहीं है जो तुम समझ रही हो।")],
 "AAKASH stands one step nearer SUMAN, palms still half-raised and lowering. SUMAN's arms are folded. NAINA is a soft shape behind AAKASH's right shoulder.",
 "SUMAN holds screen-left, AAKASH screen-right; the camera never crosses between them.")

add(3, ["suman","aakash","naina"], "ghar_night", 2,
 "AAKASH stands with palms lowering. SUMAN's arms are folded. NAINA is behind his right shoulder.",
 ["SUMAN turns her head and holds a look at NAINA for two full seconds, then turns back to AAKASH.",
  "Her arms unfold and both hands lift away from her sides, palms up; a short breath escapes that is almost a laugh, and her eyes fill.",
  "She speaks; NAINA lowers her head and looks at the floor and keeps it there."],
 "Handheld arc around SUMAN that keeps her centred, beginning only when her head turns toward NAINA; it catches NAINA's lowered head in the background at the end of the move.",
 [("SUMAN","क्या समझूँ मैं? आधी रात को मेरे पति के कमरे में एक जवान लड़की... और मैं आँखें बंद कर लूँ?")],
 "SUMAN stands centre-left with both hands still raised away from her sides, eyes wet. NAINA's head is down. AAKASH is between them, still.",
 "SUMAN screen-left, AAKASH and NAINA screen-right; no side swaps.")

add(4, ["suman","aakash","naina"], "ghar_night", 3,
 "SUMAN stands with hands raised, eyes wet. NAINA's head is lowered. AAKASH is between them.",
 ["NAINA lifts her head and takes one small step out from behind AAKASH's shoulder, bringing her hands together in front of her.",
  "Her eyes fill and spill; she holds the folded hands at chest height.",
  "She speaks; on the word SUMAN's chin lifts and she draws back half a pace."],
 "Slow push-in on NAINA, who sits in the right third, the blurred edge of AAKASH's left shoulder holding the frame edge beside her. It holds on her until she finishes, then a single cut-width reframe to SUMAN.",
 [("NAINA","दीदी, प्लीज़... मेरी बात एक बार सुन लो।")],
 "NAINA stands clear of AAKASH's shoulder, hands folded at her chest, face wet. SUMAN has drawn back half a pace, chin raised.",
 "NAINA and AAKASH hold screen-right, SUMAN screen-left throughout.")

add(5, ["suman","aakash","naina"], "ghar_night", 4,
 "NAINA stands with hands folded at her chest. SUMAN has drawn back half a pace, chin raised.",
 ["SUMAN's hand cuts once through the air in front of her, flat and fast.",
  "She advances two quick paces toward NAINA; AAKASH moves sideways to stay between them and NAINA stops moving entirely.",
  "She speaks through it, chest rising and falling hard."],
 "A fast reframe to SUMAN as her hand cuts, then a lateral track that follows her advance, holding AAKASH's shifting body in the frame between her and NAINA. The camera stays on its own side of the room.",
 [("SUMAN","दीदी? खबरदार जो मुझे दीदी कहा! सौतन बनकर आई है मेरे घर में, और ऊपर से रिश्ता जोड़ रही है?")],
 "SUMAN stands two paces further into the room, breathing hard, hand still low from the cutting gesture. AAKASH is squarely between her and NAINA, who has not moved.",
 "SUMAN screen-left, AAKASH centre, NAINA screen-right; no side swaps.")

add(6, ["suman","aakash","naina"], "ghar_night", 5,
 "SUMAN stands breathing hard. AAKASH is between her and NAINA. Nobody has moved for a moment.",
 ["Nothing happens for two full seconds: the three hold their positions, only breathing, the curtain moving very slightly.",
  "A single tear leaves NAINA's eye and runs down; she does not wipe it and does not blink.",
  "SUMAN's shoulders drop a little on an exhale; no one speaks for the rest of the shot."],
 "A slow crane up and back that begins on the held tableau and ends wide, all three in the lit room with the dark window behind. The move is continuous and unhurried.",
 [("NARRATOR","जिस औरत को सुमन अपनी सौतन समझकर नफ़रत कर रही थी, उस एक शब्द दीदी के पीछे छुपा था एक ऐसा सच, जो अभी किसी को पता नहीं था।")],
 "Wide frame: SUMAN left, AAKASH centre, NAINA right, all three standing still. The camera is high and back.",
 "Screen sides unchanged: SUMAN left, NAINA right.")

add(7, ["suman","aakash","naina"], "ghar_night", 6,
 "The three stand apart, still, after a silence. NAINA's face is wet.",
 ["AAKASH steps fully across in front of NAINA, putting his body between her and SUMAN.",
  "His left arm comes out and back, palm toward NAINA, holding her behind him; NAINA's shoulder and half her face stay visible past his arm.",
  "He speaks, his eyes not leaving SUMAN; SUMAN's mouth opens slightly and stays open."],
 "A steady medium two-shot from SUMAN's side of the room, AAKASH and NAINA in the right two-thirds. A small push-in begins the moment his arm comes out. The camera does not cross the axis.",
 [("AAKASH","सुमन, तुम्हें जो कहना है मुझे कहो। इस पर एक उँगली भी मत उठाना।")],
 "AAKASH stands squarely in front of NAINA, left arm still out behind him, palm back. NAINA is half-hidden behind his arm. SUMAN faces them, lips parted.",
 "AAKASH and NAINA hold screen-right, SUMAN screen-left.")

add(8, ["suman","aakash","naina"], "ghar_night", 7,
 "AAKASH stands shielding NAINA with his arm out behind him. SUMAN faces them, lips parted.",
 ["SUMAN's eyes fill and overflow; she does not wipe them.",
  "Her right arm sweeps out toward the two of them and holds there, then her left hand comes flat against her own chest.",
  "She speaks with her hand still on her chest, her voice breaking in the middle of the line."],
 "A slow dolly-in on SUMAN, holding her in the centre of the frame; AAKASH and NAINA sit soft and out of focus behind her sweeping arm.",
 [("SUMAN","देख लिया... देख लिया सबने! अपनी पत्नी छोड़कर पति इस बाहरी लड़की के आगे ढाल बनकर खड़ा है। यही दिन देखना बाकी था मेरा।")],
 "SUMAN stands centre frame, left hand flat on her chest, face wet, arm lowered. AAKASH and NAINA are soft behind her.",
 "SUMAN screen-left of the axis, AAKASH and NAINA screen-right.")

add(9, ["suman","aakash","naina"], "ghar_night", 8,
 "SUMAN stands with her hand on her chest, face wet. AAKASH still shields NAINA.",
 ["AAKASH's arm lowers from in front of NAINA and his head moves slowly side to side, twice.",
  "He lifts one hand as if to explain, holds it up for a beat, and lets it fall back to his side.",
  "He speaks quietly; his jaw tightens after the last word and his eyes go down to the floor."],
 "An intimate close-up on AAKASH with a faint handheld sway, SUMAN's shoulder soft in the foreground at the frame edge. No camera move once he begins speaking.",
 [("AAKASH","तुम गलत समझ रही हो। पर अभी मैं तुम्हें कुछ बता नहीं सकता... मैंने एक वादा किया है।")],
 "AAKASH stands with both arms at his sides, head lowered, eyes on the floor. SUMAN's shoulder fills the foreground edge.",
 "The foreground shoulder at the frame edge is SUMAN's; AAKASH holds screen-right.")

add(10, ["suman","aakash","naina"], "ghar_night", 9,
 "AAKASH stands with his head lowered. SUMAN faces him. NAINA is behind him.",
 ["SUMAN's head tips back and a short hard breath comes out of her.",
  "Her hand flicks out toward NAINA, dismissive, and stays extended.",
  "She speaks; on the last word NAINA's whole body flinches back as if struck."],
 "A two-shot that snaps from SUMAN's face to NAINA's the moment the hand flicks out, then holds on NAINA for the flinch.",
 [("SUMAN","वादा? किससे किया वादा? इससे? अपनी रखैल से?")],
 "SUMAN's hand is still extended toward NAINA. NAINA has recoiled a half-step, shoulders drawn in. AAKASH's head has come up.",
 "SUMAN screen-left, NAINA screen-right; no swap.")

add(11, ["suman","aakash","naina"], "ghar_night", 10,
 "NAINA has recoiled, shoulders drawn in. SUMAN's hand is still extended. AAKASH's head has come up.",
 ["NAINA backs until her shoulders meet the wall and stops there.",
  "Her head shakes quickly, twice, and her hands come up clasped in front of her; tears run freely.",
  "She speaks against the wall; AAKASH's jaw tightens and he turns his head toward SUMAN."],
 "A push-in on NAINA against the wall from slightly below her eye line; AAKASH's tightening face stays at the edge of the frame. The move ends as she starts to speak.",
 [("NAINA","ऐसा मत कहो दीदी... भगवान के लिए ऐसा मत कहो। तुम्हें कुछ नहीं पता।")],
 "NAINA stands with her back against the wall, hands clasped at her chest, face wet. AAKASH has turned toward SUMAN, jaw set.",
 "NAINA screen-right against the wall, SUMAN screen-left.")

add(12, ["suman","aakash","naina"], "ghar_night_door", 11,
 "NAINA is against the wall with her hands clasped. AAKASH has turned toward SUMAN. The front door stands open on the dark street.",
 ["SUMAN's arm swings out and her finger jabs twice toward the open door.",
  "She holds the arm rigid, pointing, and her whole body turns to follow it.",
  "She speaks; NAINA's hands close around her own dupatta and she does not move from the wall."],
 "A whip-pan that follows SUMAN's arm to the open door and the darkness beyond, then snaps back to her face and holds.",
 [("SUMAN","निकल जा मेरे घर से! अभी, इसी वक्त! फिर कभी इस दरवाज़े पर कदम मत रखना!")],
 "SUMAN stands with her arm rigid and still pointing at the open door. NAINA is against the wall gripping her dupatta. AAKASH stands between them.",
 "The open door is screen-right; SUMAN points across frame from screen-left.")

add(13, ["suman","aakash","naina"], "ghar_night_door", 12,
 "SUMAN's arm is rigid, pointing at the open door. NAINA grips her dupatta at the wall. AAKASH stands between them.",
 ["The curtain by the open door lifts on a draught and settles; nobody moves.",
  "NAINA's eyes go to the open doorway and stay there.",
  "SUMAN's pointing arm does not drop for the rest of the shot."],
 "A slow pull-back and crane-up that frames the open door between the three of them, the cold street darkness at the centre of the composition.",
 [("NARRATOR","सुमन ने नफ़रत में वो दरवाज़ा दिखा दिया, जिसके पीछे उसकी अपनी ज़िंदगी का सबसे बड़ा रिश्ता खड़ा था। पर तकदीर को अभी बहुत खेल खेलना बाकी था।")],
 "Wide frame with the open door at centre, SUMAN left with her arm still raised, NAINA right at the wall, AAKASH between. The curtain hangs still.",
 "Door centre, SUMAN left, NAINA right.")

add(14, ["suman","aakash","naina"], "ghar_night_door", 13,
 "SUMAN's arm is still raised toward the open door. NAINA stands at the wall. AAKASH is between them.",
 ["AAKASH turns to NAINA and reaches out; his hand closes around hers and draws it down from her chest.",
  "He walks her two steps away from the door and releases her hand, then turns his body to face SUMAN.",
  "He speaks facing SUMAN; NAINA's head comes up and she looks at the back of his shoulder."],
 "A medium shot that tracks AAKASH's hand taking NAINA's, then tilts up to his face as he turns; SUMAN's reaction is caught in a reframe at the end.",
 [("AAKASH","तुम कहीं नहीं जाओगी। ये घर जितना सुमन का है, उतना ही तुम्हारा भी।")],
 "NAINA stands two steps from the wall, her hand fallen to her side. AAKASH faces SUMAN squarely. SUMAN's raised arm has dropped.",
 "AAKASH and NAINA screen-right, SUMAN screen-left.")

add(15, ["suman","aakash","naina"], "ghar_night", 14,
 "AAKASH faces SUMAN. NAINA stands behind him, hand at her side. SUMAN's arm has dropped.",
 ["SUMAN's weight goes back onto her heel and she takes one unsteady step backwards.",
  "Her hand finds the arm of the sofa and grips it; her shoulders begin to shake and tears come.",
  "She speaks with her hand still on the sofa, the voice cracking twice."],
 "A slow push-in on SUMAN with a subtle handheld tremor that increases as she takes the step back. AAKASH and NAINA are soft behind her.",
 [("SUMAN","मेरे घर पर इसका हक़? आकाश, तुमने तो हद ही कर दी। पाँच साल की मेरी शादी... सब मिट्टी में मिला दी तुमने एक रात में।")],
 "SUMAN stands bent slightly, one hand gripping the sofa arm, face wet and shoulders shaking. AAKASH and NAINA stand still behind her.",
 "SUMAN screen-left at the sofa, AAKASH and NAINA screen-right.")

add(16, ["suman","aakash","naina"], "ghar_night", 15,
 "SUMAN grips the sofa arm, weeping. AAKASH and NAINA stand behind her.",
 ["AAKASH watches her for two full seconds without moving or speaking.",
  "His eyes close briefly and open again; his hands stay at his sides.",
  "He speaks quietly and evenly, and his gaze does not leave her."],
 "A slow dolly-in on AAKASH's face, SUMAN's shaking shoulder soft in the foreground. The move begins only after the two seconds of silence.",
 [("AAKASH","एक दिन तुम खुद मुझसे माफ़ी माँगोगी सुमन। बस उस दिन का इंतज़ार करना।")],
 "AAKASH stands with his hands at his sides, eyes steady on SUMAN. SUMAN is bent at the sofa, still gripping its arm.",
 "The foreground shoulder is SUMAN's; AAKASH holds screen-right.")

add(17, ["suman","aakash","naina"], "ghar_night_door", 16,
 "SUMAN is bent at the sofa. AAKASH stands with his hands at his sides. The front door is open.",
 ["SUMAN straightens and snatches a shawl and a small handbag from the sofa in one movement.",
  "She turns on her heel toward the open door, the shawl swinging with the turn.",
  "She speaks over her shoulder without stopping, and keeps walking toward the door."],
 "A tracking shot that follows SUMAN from the sofa to the door, keeping her in the left third; AAKASH and NAINA fall away into the widening background behind her.",
 [("SUMAN","माफ़ी? मैं? रख लो अपना घर, अपनी ये नई औरत... मैं जा रही हूँ अपनी माँ के घर।")],
 "SUMAN is at the open doorway, half-turned away, shawl over one arm and bag in the other hand. AAKASH and NAINA stand small and still deep in the room behind her.",
 "SUMAN moves from screen-left toward the door at screen-right; the camera stays behind her.")

add(18, ["aakash","naina"], "ghar_ext", 17,
 "A car stands at the kerb outside the house with its door closing. AAKASH and NAINA stand in the lit doorway behind it.",
 ["The car pulls away; its red tail-lights slide out of frame and the street sound thins to nothing.",
  "AAKASH stays in the doorway watching the empty street; NAINA, beside him, wipes her face once with the back of her hand.",
  "AAKASH steps back inside and pushes the door slowly closed until only a thin warm line is left, then it goes dark."],
 "A slow crane that starts on the departing car in the street, lifts, and comes round to the lit doorway where AAKASH and NAINA stand, ending square on the closing door.",
 [("NARRATOR","उस रात सुमन अपने मायके चली गई। पर आकाश जानता था कि जो तूफ़ान उसके घर में आया है, वो असल में एक बिछड़े हुए रिश्ते की आहट है।")],
 "The street is empty and dark. The door is closed; the warm light from inside is gone from the street.",
 "The doorway holds screen-right, the empty street screen-left.")

add(19, ["saas","aakash","naina"], "ghar_lamp", 18,
 "The living room, later, lit only by one warm table lamp. AAKASH stands near the sofa; NAINA stands apart from him. An inner doorway is dark.",
 ["SAAS comes through the inner doorway into the lamplight and stops when she sees the two of them.",
  "Her eyes move from AAKASH to NAINA and back; one hand lifts and gestures toward NAINA.",
  "She speaks with the hand still raised; NAINA looks at the floor and AAKASH turns to face his mother."],
 "SAAS enters from the left edge; the camera settles into a three-way medium shot and pushes gently toward her face as she begins to speak.",
 [("SAAS","बेटा, ये सब क्या हो रहा है? पूरा मोहल्ला बातें बना रहा है। ये लड़की कौन है जो हमारे घर में रह रही है?")],
 "SAAS stands just inside the inner doorway, hand lowering. AAKASH faces her. NAINA stands apart, looking down.",
 "SAAS holds screen-left, AAKASH centre, NAINA screen-right for the whole shot.")

add(20, ["saas","aakash","naina"], "ghar_lamp", 19,
 "SAAS stands inside the doorway. AAKASH faces her. NAINA looks at the floor.",
 ["AAKASH crosses to SAAS and takes both her hands in his.",
  "He lowers their joined hands between them and holds them there.",
  "He speaks; his eyes flick once to NAINA and back to his mother."],
 "A two-shot of AAKASH and SAAS with a slow dolly-in that begins as he takes her hands; NAINA stays soft in the background, her face turned up slightly.",
 [("AAKASH","माँ, बस थोड़ा वक्त दे दो। जिस दिन सच सामने आएगा, हम सब शर्मिंदा होंगे कि हमने इसे कैसे-कैसे शब्द कहे।")],
 "AAKASH and SAAS stand holding hands between them. NAINA is behind, her head now up.",
 "SAAS screen-left, AAKASH beside her, NAINA screen-right.")

add(21, ["saas","aakash","naina"], "ghar_lamp", 20,
 "AAKASH and SAAS stand with their hands joined. NAINA stands behind them, head up.",
 ["NAINA steps forward to SAAS and brings her hands together in front of her.",
  "Her head lowers in a slow bow and stays down.",
  "She speaks with her head still bowed, her voice unsteady on the last phrase."],
 "A push-in on NAINA's bowed posture, then a slow tilt up to SAAS's face, which softens without losing its firmness.",
 [("NAINA","आंटी जी, मैं आपके बेटे की ज़िंदगी में कोई गलत जगह लेने नहीं आई। मैं तो बस... एक टूटा हुआ रिश्ता जोड़ने आई हूँ।")],
 "NAINA stands with her head bowed and hands folded. SAAS looks at her steadily. AAKASH has released his mother's hands.",
 "NAINA screen-right, SAAS screen-left.")

add(22, ["saas","aakash","naina"], "ghar_lamp", 21,
 "NAINA stands bowed with folded hands. SAAS looks at her. AAKASH stands beside them.",
 ["SAAS's head moves slowly side to side, once.",
  "Her right hand comes up, palm out, and stays at chest height.",
  "She speaks firmly, her eyes fixed on NAINA, who does not raise her head."],
 "A reverse to a firm medium of SAAS with a small push-in; NAINA's bowed head sits at the lower edge of the frame.",
 [("SAAS","रिश्ते ऐसे नहीं जोड़े जाते, बेटी, कि किसी की बसी-बसाई गृहस्थी उजड़ जाए।")],
 "SAAS stands with her hand still raised, palm out. NAINA's head is still bowed. AAKASH stands to the side.",
 "SAAS screen-left, NAINA screen-right.")

add(23, ["saas","aakash","naina"], "ghar_lamp", 22,
 "SAAS stands with her hand raised. NAINA's head is bowed. AAKASH stands to the side.",
 ["NAINA raises her head and nods once, slowly.",
  "She wipes her eyes with the edge of her dupatta and her eyes go to the front door.",
  "She speaks quietly; AAKASH's body stiffens and he turns sharply toward her."],
 "A slow push on NAINA's face, then a quick rack-focus past her to AAKASH's stiffening reaction behind.",
 [("NAINA","आप सही कह रही हैं। मुझे नहीं आना चाहिए था। मैं कल सुबह चली जाऊँगी।")],
 "NAINA stands with her head up and her dupatta still at her cheek, looking toward the door. AAKASH has turned toward her, body tense. SAAS's hand has lowered.",
 "NAINA screen-right, AAKASH centre, SAAS screen-left.")

add(24, ["saas","aakash","naina"], "ghar_lamp", 23,
 "NAINA looks toward the door. AAKASH has turned toward her, tense. SAAS's hand has lowered.",
 ["AAKASH takes two quick steps toward NAINA and his hand comes up, palm out, stopping her.",
  "His voice rises and his eyes glisten; NAINA turns back to face him.",
  "He finishes the line; SAAS's mouth opens slightly and she looks at her son."],
 "A push-in on AAKASH's face as he steps in; brief reframes catch SAAS's and NAINA's surprise without cutting away.",
 [("AAKASH","नहीं नैना! तुम कहीं नहीं जाओगी। मैंने पाँच साल तुम्हें ढूँढा है। अब मैं तुम्हें दोबारा नहीं खोऊँगा।")],
 "AAKASH stands close to NAINA with his hand still half-raised. NAINA faces him. SAAS stares at her son, lips parted.",
 "AAKASH centre, NAINA screen-right, SAAS screen-left.")

add(25, ["saas","aakash","naina"], "ghar_lamp", 24,
 "AAKASH stands close to NAINA, hand half-raised. NAINA faces him. SAAS stares at her son.",
 ["AAKASH's hand lowers to his side and stays there; he does not speak again.",
  "His breathing steadies; the lamp light catches the wet along his lower lids.",
  "NAINA's eyes fill as she watches him, and SAAS's expression slowly changes from shock to thought."],
 "A very slow push-in on AAKASH's face; SAAS and NAINA fall softly out of focus on either side in the warm lamplight.",
 [("NARRATOR","पाँच साल... आकाश हर छुट्टी, हर बचत, हर उम्मीद इसी एक तलाश में लगा चुका था।")],
 "AAKASH stands still with his hands at his sides, eyes wet. NAINA watches him. SAAS's face has settled into thought.",
 "AAKASH centre, NAINA screen-right, SAAS screen-left.")

add(26, ["saas","aakash","naina"], "ghar_lamp", 25,
 "AAKASH stands with his hands at his sides. NAINA watches him. SAAS is thoughtful.",
 ["AAKASH turns his head and looks at NAINA; the look holds, protective rather than romantic.",
  "SAAS watches her son watching NAINA and her eyes narrow very slightly in thought.",
  "Nobody speaks; the lamp flickers once and steadies."],
 "A slow lateral drift across the three faces — NAINA, then AAKASH, then SAAS — ending held on AAKASH's guarded eyes.",
 [("NARRATOR","पर उसने ये राज़ अपनी पत्नी से भी क्यों छुपाया था? इसकी वजह और भी गहरी थी।")],
 "AAKASH looks at NAINA. SAAS watches him. All three are still in the lamplight.",
 "NAINA screen-right, AAKASH centre, SAAS screen-left.")

json.dump(S, open(f"{P}/scenes_A.json","w"), ensure_ascii=False, indent=1)

def build(sid, sc):
    chars, ch = sc["chars"], sc["chain_from"]
    n = len(chars)
    roles = []
    for i,c in enumerate(chars):
        roles.append(
          f"@Image{i+1} controls only the identity and clothing of {ROLE[c]} — the exact person shown in "
          f"@Image{i+1}, face and hair unchanged, wearing exactly the outfit from that plate. Do not alter "
          f"their features. Do not copy the white studio background, the split-screen layout, the passport "
          f"framing or the standing pose from @Image{i+1}.")
    if ch:
        roles.append(
          f"@Image{n+1} is a still frame from the moment immediately before this shot. It controls only the "
          f"room, its light and where the people are standing, which carry forward unchanged. Do not copy its "
          f"framing or treat it as the opening composition.")
    beats = sc["beats"]
    tl = (f"0–3.5 seconds: {beats[0]}\n3.5–7 seconds: {beats[1]}\n7–10 seconds: {beats[2]}")
    spoken = [l for l in sc["lines"] if l[0] != "NARRATOR"]
    narr   = [l for l in sc["lines"] if l[0] == "NARRATOR"]
    names  = ", ".join(ROLE[c].split(",")[0] for c in chars)
    if spoken:
        lines_txt = " ".join(f'{s} speaks in Hindi: "{t}"' for s,t in spoken)
        who = ", ".join(s for s,_ in spoken)
        audio = (f"Dialogue in this shot: exactly {len(spoken)} line{'s' if len(spoken)>1 else ''}, spoken in "
                 f"Hindi. {lines_txt} Only {who} speak{'s' if len(spoken)==1 else ''}; everyone else in frame "
                 f"keeps their mouth closed throughout. ")
    else:
        audio = ("No character speaks in this shot and every mouth in frame stays closed. ")
    if narr:
        audio += (f'A single calm male narrator voice-over is heard in Hindi, separate from the room: '
                  f'"{narr[0][1]}" ')
    audio += ("Everything else is the room itself — footsteps on stone floor, fabric movement, breath, the "
              "faint hum of the night outside. No background voices, no other people speaking, no voices from "
              "another room or the street, no television, no radio, no crowd chatter, no music.")
    parts = [
      "FORMAT\n10 seconds, 16:9 horizontal, one continuous take, real time.",
      "LOOK\n" + LOOK,
      "REFERENCE ROLES\n" + "\n".join(roles),
      "CAST\nThe only people in this shot are " + names + ". Every figure, shoulder, hand or reflection at any "
      "frame edge belongs to one of them and to no one else.",
      "SETTING\n" + LOC[sc["loc"]],
      "STARTING STATE\n" + sc["start"],
      "TIMELINE\n" + tl,
      "CAMERA\n" + sc["camera"],
    ]
    cont = "Identity, faces and outfits stay exactly as the reference plates through every beat. " + (sc["sides"] or "")
    parts.append("CONTINUITY\n" + cont.strip())
    parts += ["AUDIO\n" + audio, "ENDING STATE\n" + sc["ending"],
      "CONSTRAINTS\nNo cuts. No slow motion. No repeated or looped action. No duplicate or invented people. "
      "No on-screen text of any kind, no subtitles, no captions, no watermark, no logo, no signage. No change "
      "of clothing, no change of room, no character swapping faces with another."]
    open(f"{P}/docs/s{sid}.txt","w",encoding="utf-8").write("\n\n".join(parts) + "\n")

for k,v in S.items(): build(k,v)
ln = [len(open(f"{P}/docs/s{k}.txt",encoding='utf-8').read()) for k in S]
print(f"built {len(S)} docs, chars min={min(ln)} max={max(ln)} (cap 5000)")
