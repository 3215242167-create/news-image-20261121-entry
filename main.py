#!/usr/bin/env python3
"""One 1024x1024 newspaper front page: the world news of 21 November 2026.

Run it and it paints the whole page from code and saves entry.png in
the output directory. It needs nothing but the Python standard
library: no Pillow, no font files, no network, no randomness, no
clock. Run it twice and the two files are byte for byte the same.

The first version of this entry was drawn with PIL and the Noto faces
in fonts/. That worked on a full machine, but the grader runs
`python3 -P -s /bot/main.py` inside python:3.13-slim, which has
neither Pillow nor those fonts, so the import failed at once and the
graded run never finished. This version carries no such dependency:
it paints on a bytearray, draws its own lines, writes its own PNG
bytes (zlib + struct), and sets its type from 1-bit bitmaps that were
lifted out of the bundled Noto faces once, on the build machine. The
letter shapes travel as data; the drawing is all code.

What is on the page: THE WORLD TODAY for Saturday 21 November 2026.
The Antalya climate talks running past their deadline, the plot
stopped in Denmark, the tanker fire off Oman, the strikes on Kyiv,
Cyclone Akvan coming ashore, the Anthropic debut, and two short
items below. Nothing on it is a photograph or generated imagery; the
program sets every word itself.

Usage:  mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import base64
import binascii
import math
import os
import struct
import zlib

WIDTH = 1024
HEIGHT = 1024
MARGIN = 46

# The page's colours. PAPER is the sheet, INK the main text; the
# bands are TEAL / TEAL_DARK, the thin rules GOLD, kickers RUST.
PAPER = (250, 247, 238)
INK = (24, 28, 32)
BODY_INK = (52, 58, 64)
TEAL = (13, 58, 69)
TEAL_DARK = (9, 42, 50)
GOLD = (198, 155, 58)
RUST = (178, 58, 32)
SLATE = (88, 96, 104)
HAIRLINE = (196, 188, 172)
CARD = (255, 253, 247)
CHIP = (13, 58, 69)
WHITE = (255, 255, 255)
PALE = (235, 238, 240)


# ---------------------------------------------------------------- PNG encoder

def encode_png(w, h, rgb):
    """Turn raw RGB bytes into a PNG: 8-bit, colour type 2, no filtering."""
    rows = bytearray()
    step = w * 3
    for y in range(h):
        rows.append(0)
        rows += rgb[y * step:(y + 1) * step]

    def pack(tag, payload):
        body = tag + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(
            ">I", binascii.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    parts = [b"\x89PNG\r\n\x1a\n",
             pack(b"IHDR", header),
             pack(b"IDAT", zlib.compress(bytes(rows), 6)),
             pack(b"IEND", b"")]
    return b"".join(parts)


# ---------------------------------------------------------------- canvas

class Canvas:
    """RGB pixels in one flat bytearray, plus the shapes the page needs."""

    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(bg) * (w * h)

    def set(self, x, y, colour):
        if 0 <= x < self.w and 0 <= y < self.h:
            at = (y * self.w + x) * 3
            self.px[at:at + 3] = bytes(colour)

    def rect(self, x, y, w, h, colour):
        """Paint the half-open box [x, x+w) by [y, y+h), clipped to the page."""
        left = max(0, int(x))
        top = max(0, int(y))
        right = min(self.w, int(x + w))
        bottom = min(self.h, int(y + h))
        if right <= left or bottom <= top:
            return
        fill = bytes(colour) * (right - left)
        row = self.w * 3
        for yy in range(top, bottom):
            at = yy * row + left * 3
            self.px[at:at + len(fill)] = fill

    def line(self, x0, y0, x1, y1, colour, width=1):
        """A Bresenham line; a width above 1 stamps a square at each step."""
        adx = abs(x1 - x0)
        ady = -abs(y1 - y0)
        stepx = 1 if x0 < x1 else -1
        stepy = 1 if y0 < y1 else -1
        error = adx + ady
        half = width // 2
        x, y = x0, y0
        while True:
            self.rect(x - half, y - half, width, width, colour)
            if x == x1 and y == y1:
                return
            twice = 2 * error
            if twice >= ady:
                error += ady
                x += stepx
            if twice <= adx:
                error += adx
                y += stepy

    def disc(self, cx, cy, r, colour):
        """A filled disc of radius r, one scanline at a time."""
        for yy in range(cy - r, cy + r + 1):
            off = yy - cy
            half = int(math.sqrt(max(0, r * r - off * off)))
            self.rect(cx - half, yy, 2 * half + 1, 1, colour)

    def rounded(self, x, y, w, h, r, colour):
        """A filled rounded box covering [x, x+w] by [y, y+h]."""
        # A plain box for the middle, four discs for the corners, and
        # two bars joining them: the bars cover the straight edges.
        self.rect(x, y + r, w + 1, h - 2 * r + 1, colour)
        self.rect(x + r, y, w - 2 * r + 1, h + 1, colour)
        for cx, cy in ((x + r, y + r), (x + w - r, y + r),
                       (x + r, y + h - r), (x + w - r, y + h - r)):
            self.disc(cx, cy, r, colour)


# ---------------------------------------------------------------- bitmap font
# The type on this page comes from ten small tables, each one lifted
# from a bundled Noto face at exactly the pixel size its job needs,
# so glyphs are always painted 1:1, never scaled. A glyph is a
# 1-bit picture, most-significant bit first, each row padded out to
# whole bytes, with a 1 px empty margin built into the picture. The
# tables are stored as one long byte string: every glyph picture is
# laid end to end, the lot is squeezed with zlib and written out in
# base85 as _BLOB, and INDEX keeps, per table, the characters in
# order plus one "advance,width,height,top,offset,length" record per
# glyph. "top" is where the ink starts below the face's ascender
# line, which is what keeps a small letter like r, a comma, or a
# descender like y sitting on the same baseline as the capitals
# instead of floating at the top of the line.

"""Embedded bitmap font tables (generated; see work/gen_fonts.py)."""

_BLOB = (
    "c-qxk&5tC>Rev=(boN3`W%l-HobAretnt8dvDoaLkzJ#y>Fk5Wl|O(>t`>1ZR#{vMsWla5EzH5Py|=Zr!2Sv28%QfTmO(5B%fQhRf*6g&-t3%PN)%Q6-iyeu`smqREE)2>c$t+MU+=~His&ZdD_^hIE1G(1ozM()L<Q)9qnDsJUO@?z{y)$hjP|c|y#&%=ZMep-?S@PL",
    "+9x45Cy>63)@w6Z>j4uIQZO0!34LLLRr%j_;K*U0L`)`3=FCFXV=4!ePbgjaYlHhhGw%x`xvz=TVAoxtA&Wu{`ghi?b!qR5@`l(%=e{sJU`6hJb75}EJuh)j`OZ>alDi+K<)OV-xCea4`(Q=&Jy?cB{wi$mc<-<ASl`F2@#FgLt;7P92Sy+$+%H97gXS)b)pu3jskyVn",
    "7WG|l_cc#=q%wdY0^@_7RC}0ouDvC9Fj(2{c@hostk&96pQ+iV0n_q}(S3b($L-F?&d|-)&fIbVj!ey+<#g*xMa^JJ=ms=5LQAGtJf`An($yED%eJ3f=tBB;9)!pJv_oIW94vh<b)K(neM`%hE~=L1%a(RW4|vreIwg)mv6IM6kM)&s{(qDl?jTV^CQPbLFM;3ET0aq*",
    "vkZ00($fLUO8ZNp;=X*A537?<)uFnfyU<)qcVpeB+M?|o+^m)@wQ~+i;X-)HmE+EGx}nQuhl*HoOC>sp&!IoCRHCYQANsDP;wikA4m|NCgC1o&q8>FZU07PyG;nK^cWAoYq`|7Dm-Vwuf=ymEl>IiS$Ilx4Ec(F#u>lfJG0PE}D;jcTI&{=>!f_%L9zv^RGVd`v95-Y5",
    "R#?=f%vFilR5RDrpq=abhRn}WCG<O;yyc(BX)&mD{VSrjH!Qr`c4Jpi32zDQ@GGc$P(caO3ObOMn15OZT@sYw!z+auQ3@exOR8Fn#9b_SIH}9Od?CW95YY=E`yz}q6C!=?Bu$n61uMYPDy+7qWuOO@Z@kinQ};EV6t|F~ZAtf(`g>iUdEijzl}MQ@BuOjqvcNd`+K$;y",
    "pc3U`DX>3YqP16{nOB1NW>7JKL@l8u53{l)y_U4~Y%}h_ccil2%Rn-u3~s04S3Rvak`?*?#p}61$(2{8T=brzY@Hl+(FSe3HIF2+*k3BU40Wk54!ST$7=)qpU1;39P`E)`yg{d97J2~hwX)ts48(VxgKsHh%Mc~T?<v|}pyX(uqJF?@(A^KDY^6$6l>203On-uccS-KP",
    "{fdgua(1P&0-sd*FPA{P_N&S-=YCoEtQyy1N%@M`Q<l_r^nBfvz~rd)IZDZ80o_<*IXON18-ya*)RVMlQuzyr@>2}_%N5u_(pfEB+s{3o%9pvROFIG_E%YJyu1-CZdYVxz5FRC1i5KUb9SdoOzKK0E^~{B5a#TYrOx%gq(_-TQ@iBJthQYrcN=#>!I}Jh97xV-J;{*<T",
    "#p?7|3h3D^v%eFSoD82|vdyyLKarB^9BO$@!S_Hfn)=+<TUXY(=dEommJ2PVTIj$as-Zw;wv;hUY9eJ&ahXY>Wr1RBc>>Wb*lp-mkJF9FAvq@adkH`G9BZVPQc}fbB?)3vTyrUnPd&uEcs`R34|>au=P#DfM5rEOER+w_m%I%M_^e`e`t}Aj`QVGurSt$Us{CUp`ch0v",
    "X#Zk8^m+AOSkC>AG5e2~ttS%Ch<>;{hcxgl{q}YVo}sLuQA=cSWjhLlz`M(8@Urq=!kHV184lq>Ep}gCk5&&wdsXd$Ka)l5fS_k3Y`%FnF77KVDRvyYoJaZjoCj7%Z#fU%^410W`+a4wdV-aK-Mr+`$uV^0><&e}qBxriH0BST@Yg@V#t5ppY#k-Xmq1QcIx!7889>7Z",
    "9M2@C)uoPW&c=9(^NrHmY&RjUU*_Euo)fk;C8<h$piaCk^yO2^)g-&CCCG^%ze%PvO(et!PKhzO$)Awwd36dAS9FHvu<eAB;5uv?%<1gEoj*uZ%n@IcSC=}OlKFA6DKkQ%g$Z3?t`@I2;ZFaJf)Ctiv$GQED<wNXu4DswFy=j(Q&MtH$yhS-8@#`e3PCNcfB_qZ6lS!5",
    "d));ag1unDZXjN=U@NX>CoWTrWrq8KUh%zO(>H0Em(%f-u<Y6|2PMriyva?ft+3)^Y9{8P`7=Y;T~5JPP83dPiM*^Bovf0k0xO#n_-H@cPF51<f3{1(HgqiEm;4D*t+tlZb#NeSkcy+*lnSq&Y({8WGUwo3e@kD>`^FglzsnKbYX7oYcE0ag^Lt3<ih?=zP?8wbNkUNT",
    "7%E&P?a|r<O=5l-qv3?>jAj(fs7VnyInix>I|Pp+YCM{A<?Z?wu`F;pxtNp98CDFQz7BR;PUUpsGdhCnn(trc*!dkF69@2<x*h_xpoQZO`&DdelMvErAc@i{;9Zhj9I-jawCQIua5xoge&Q1<`1TO9PUWGopGgz`+OZr>oxL=BR(8l>H|@Egq;&p=&FX5OS@AwSty;z2",
    "{N4IHPk$za;DB<tJg9wrN+wl;+N8#u855T#0nP=dCP@SXL0_=;XSHN0_zU#o7Cjc63T-qY_;V4{%5LT)oR*9TIgB5X5Bz|9ST7K^9Y_pgR8wEj)AQOO=F{oqYC64|OrK1q-<-$4m?!@^OFo^AJ}HAw4C6E7zYEkZ=K`pJb^~&6EvYFwolIt%`Jfsozf70uGJpTEdaQDl",
    ">Y((h!E*4?;Dd)BAycWaM^|#v0XqzMg{ISKJWb|7$vIWRvyJg$nlIDJIwmq6=UWhXYz__WhF-wnzH{^)U5SEYH;Ig`BKvEaUFB6?T8H0v<XvAb;mGC%d)zAaA0{s|gb+aK@o9?4$XX{q`L-UU@K{f1Lg*8%urQeML&!0;HmT53ALx-86~kFPL$t2)3gSgHvPWu*(x=_P",
    "R}}X_t|@G~wDL<eBv+!dSzM;j+%p|RlK3@`C+>S0SMelnuPJ`PPgohvu+Wn-hPDSf5TDZ<9}~?oVKdi{O(@GT&>lM;EXGt4Y{w>CQLavvw*{TJm<pbLpYh~pbn**|fKLQ31e1QEhNysHMl|Ule&QuQb@GWBxL}=~upl6Sp&97_f@c>gVqgU$3lNEJo{dXuUBc+AG+;cv",
    "rA~jucmn)8b@Eb07N0wZ#A0p5Ub46WWi3{x7N!qp7&%aO`yOb7KET&?-h6*-n(r`|bjA{%G=SM=FgRxpyP@VM2kiRJ?`2t|&H-L=P`p~vV%Atz6rC!-E=8*qk&{x>$~bO=)5LL9P1pn=v2;=gr{1dQZtK`(O7SLI8{U53Z2bn%Rnb-`^GJG{h{0KvnVDH>veHa|m45hh",
    "ee!dC_9K1vSL*BsDgXvR3j8`cEYy94{-DvE5fA0<5Pc5a{5;0Qqtv5Qk51mDlV=nG-=XMFDY{S5BZ^Xr0zucSuLBd!qAbghr<NH-fLh}I`#}{=qDdB6;OC(7-$#{<vef>?&h~(hO)Wg42Nxf>KVI`_1Dq?1A};Oa`lEtJfCiSZ{#iClp9bs%=m={cZ}k;5ju4HcZ#Y4X",
    "J{l*;z9HT-le#^fzR=iE#*>+Fyc=yrwzo;Nby1%e_o{$wvmz^^BGN;BOWhJD=OJ(A%=yagD`EF06s`dU&mHTG8bh9SDSyIdE)06f+!X@kg3t@(*~+bkj_d-Fl}5yWVb!!_a=e}?uO}|_BJ*<&SPgZgCxv4e5fx|?T9~TEVa90pBVaTeIxG&z4d%=n`jCyCDll9lzNXS%",
    ")x&iG*tiO#GvITT{aBs<Se?A5PEP6clz!`!Mk9xNmJTkUJT-k)XqN0Uf*9&0^INvq7D-z`QX=bA+hhHd>J!r#MUm=FeM>uocAq2rmloo%d}9w-eSf5Qg=6UZKxXqurS8j_rc2hMz+erF%set_A&eE{BGVa|I#I8wTarW^2(TZS?VdM7VON2_hglyYc-!D9e+aoW7v3D}",
    "#B~+A4ij^%L#ly#4O}AxL1=l_Tv3sjdUI>N$z;QN<2o&Z2SCdrH?{63PV;MX2%esm(X7*VJ@;lxVG-&hbxe1Vh@H}r3N=7vcdYKX@j~jcz&at;bD~ap=dVtbNNiS1td@F+FOa*FI&BE31skpWza7%1C4<w<Myq=K{XOjAHKQ>VXGTt$qe<xGnpqR2;$yn|jLu)s`8#y}",
    "6*_){PQON9en3e~BLo^3+UWS7DOu}i1~zpx*5MYq*uq+$bvQ`1tYm1Te>B`gMAPk;k&ADv)}c7k7)eUNOFagF8Jn{BbjvBoUKbD91#^ng=K+NWlywk4@e-d<!R=OAC`H%J>=Jsb*UVAq<QRJjn0TDfefc*eo4ch>UgK;odaq99-ez=rn~JwxL)LIcEMRu!{Hc||5EJ{T",
    "ITj3%{nRp*XlEp56uh~zE;8OJgvhzhKt0yB#Q>rlxMwOJYWLR%&RX;hY#TTZgwWju#~|zRgufvrhjc%pdm-H$)BSJKTYpH&zY@Kt2EZfb9nnEbH%E007`_7Ih>uX}Z2E%#Pe{PVz(W9`#B%5VVyOMrHi&-Gm$od`sye&%7D6Z!)MsoP{eaT{kX0#ExC?D91Zo)f*g3y3",
    "T%<WxeV^vcO70ikU~}Q}6f4P8Pc-|5M>@H*-axu8!f_X*tGA!g-M^>vf28x@r~7|Q$A3hxf0dH2@^Qs5V(e(>1sr6TZMZ>qNE%QZGCUD)u5uSaEd&rp)DaMKXT`(LHN5OPR~WP2<-u!b(pZZ~EbK|_OUm`B`VQhu1*#)KF+u4o+6KPrM6*u*oI!9nyae!R1MLh=KAed#",
    "I<`&(dSHDMA451x+2clJa>K(&vahlAt=30*0AC%bn=qThOXf2*QVFYS{}g^Ay2CPv%vMS;Mn8u`dmVEBB7kw<2SvjeaA$Z7IQm}rQ^22uSK%~_!`O!JP9o78!EFr3n=1?hD5!;=pWCO9)8-#X#_6`gxUN#?O<2cI<k05;<uy7{{APzhY~;MO*@p82a_lpp-F_gYbEi5n",
    "+`si0_i7)<<EXJ_$P|xX&!vSEoya`C29wEpV0(xpTry;I;<Ahpp3c=6rc<k%J#KwVYK<_{0l7K2^jU6colGFTNa3LHi+^8=c3!!RK5iTF)3^^1KC%p}r7WR1yPe(1j<cie=xJC2W;XJ_b9nDB@4f%V4<G#S_P_Ao9HPRW(;rBPWcf#IE_!@9MruM^lk0oTv~g}}$IaQ5",
    "UFe&%3#{cf7tE!1+5I|%!0VN&b9EOx+gRCi177KySYP(unLRC_@G?|3E8}B02+z*9Xkv?OyKmp7+Yji@Z`12=kKdr<Z_v>{(9w4oT|N>QVb)EQ!YnSV0~smN76I0lks`p6%c#Fj5An9EIc-w8`&(-+*w^)qCkv?~8UEKfz>e|7%-)cE-|BwY<iPcM{wA*`WC2}-mKT?O",
    "xr<t|@<yo2-Arx%e$^`52#v=Mj+8`+HzsxKtnJNKrMno3I}EMXkD$4&OMP>G{?qgCwZJvrgsEf>9wOFs&Ff7oxCX?GL>YKCckz@!Fl_wxOs=hYZof54koQJ;le%BF$FKt58cC#eAI4id8#aEMPThps-QHGl80cg?9X}YqHNHPSA7>wCCKHu>o9@B|yhX2z!VanK`z{1n",
    "!?EMaI+@>tBjeeet0Nn$8!wQv%er)ds=$+tXlTujh8-Y}btdoL3Gao!8~)DI2Oq{CMkd;ti`|^EY0aD~3!QtjuFDR%+WM0mVh|K}QisopXy$>_%SiOH_7(%pClGu(H`oDgS737NOzgq-z<8R^audoc2AkdHWhw{XJ|7AjDrpXwwSP$^gLZOoKQcoTn~BM*1)x2yPx&O&",
    "*t0ye;@;XmlsgYZ9X^qJWcY+-I_DF?={zm#^O968(AJ$eYrpwhbNyH6{{fZTw2S",
)

INDEX = {}
INDEX["MAST"] = ("THE WORLDAY?", "38,41,42,20,0,252;47,49,42,20,252,294;38,40,42,20,546,210;13,0,0,0,756,0;61,64,42,20,756,336;46,48,44,19,1092,264;42,45,42,20,1356,252;38,40,42,20,1608,210;45,47,42,20,1818,252;44,47,42,20,2070,252;42,44,42,20,2322,252;33,35,44,19,2574,220")
INDEX["LEAD"] = ("COP31 runsitovemaflhd?", "27,29,32,14,2794,128;32,34,32,14,2922,160;26,28,32,14,3082,128;23,25,32,14,3210,128;23,25,32,14,3338,128;11,0,0,0,3466,0;21,23,25,21,3466,75;27,29,24,22,3541,96;27,29,25,21,3637,100;20,22,25,21,3737,75;14,16,34,12,3812,68;17,19,30,16,3880,90;25,27,25,21,3970,100;25,27,24,22,4070,96;23,25,25,21,4166,100;40,42,25,21,4266,150;25,27,25,21,4416,100;17,22,34,12,4516,102;14,16,34,12,4618,68;27,29,34,12,4686,136;27,29,34,12,4822,136;23,25,32,14,4958,128")
INDEX["SB25"] = ("Denmark foils\u201cRupt\u201ddxvyThbjcOgKFUNCAwI\u2019$81.3P?", "19,21,20,9,5086,60;15,17,16,13,5146,48;16,18,16,13,5194,48;25,27,16,13,5242,64;15,17,16,13,5306,48;11,13,16,13,5354,32;16,18,21,8,5386,63;7,0,0,0,5449,0;10,13,21,8,5449,42;15,17,16,13,5491,48;8,10,21,8,5539,42;8,10,21,8,5581,42;12,14,16,13,5623,32;11,13,20,9,5655,40;17,19,20,9,5695,60;16,18,16,13,5755,48;16,18,22,13,5803,66;11,13,19,10,5869,38;11,13,20,9,5907,40;16,18,21,8,5947,63;14,17,16,13,6010,48;14,17,16,13,6058,48;14,17,22,13,6106,66;14,16,20,9,6172,40;16,18,21,8,6212,63;16,18,21,8,6275,63;8,12,27,8,6338,54;13,15,16,13,6392,32;20,22,20,9,6424,60;16,18,22,13,6484,66;17,19,20,9,6550,60;14,16,20,9,6610,40;19,21,20,9,6650,60;20,22,20,9,6710,60;16,18,20,9,6770,60;17,20,20,9,6830,60;21,24,16,13,6890,48;10,12,20,9,6938,40;5,8,20,9,6978,20;14,16,23,8,6998,46;14,16,20,9,7044,40;14,16,20,9,7084,40;7,9,6,23,7124,12;14,16,20,9,7136,40;16,18,20,9,7176,60;12,14,20,9,7236,40")
INDEX["SB19"] = ("SATURDY, 21NOVEMB06CLI\u00b7\u00dcKPGFHZW?", "10,12,16,7,7276,32;13,16,16,7,7308,32;11,13,16,7,7340,32;14,16,16,7,7372,32;13,15,16,7,7404,32;14,16,16,7,7436,32;12,14,16,7,7468,32;5,7,7,19,7500,7;5,0,0,0,7507,0;11,13,16,7,7507,32;11,13,16,7,7539,32;15,17,16,7,7571,48;15,17,16,7,7619,48;12,15,16,7,7667,32;11,13,16,7,7699,32;18,20,16,7,7731,48;13,15,16,7,7779,32;11,13,16,7,7811,32;11,13,16,7,7843,32;12,14,16,7,7875,32;11,13,16,7,7907,32;7,9,16,7,7939,32;5,7,10,13,7971,10;14,16,20,3,7981,40;13,15,16,7,8021,32;12,14,16,7,8053,32;14,16,16,7,8085,32;10,12,16,7,8117,32;15,17,16,7,8149,48;11,13,16,7,8197,32;18,21,16,7,8229,48;9,11,16,7,8277,32")
INDEX["SR22"] = ("Negotiars fmnly20cuxA;hd-wpv.?", "17,19,18,8,8309,54;12,14,14,12,8363,28;14,16,19,12,8391,38;13,15,14,12,8429,28;8,10,17,9,8457,34;6,8,18,8,8491,18;12,14,14,12,8509,28;9,11,14,12,8537,28;11,13,14,12,8565,28;6,0,0,0,8593,0;8,11,18,8,8593,36;21,23,14,12,8629,42;14,16,14,12,8671,28;6,8,18,8,8699,18;11,14,19,12,8717,38;13,15,18,8,8755,36;13,15,18,8,8791,36;11,13,14,12,8827,28;14,16,14,12,8855,28;12,14,14,12,8883,28;14,17,18,8,8911,54;6,8,17,12,8965,17;14,16,18,8,8982,36;14,16,18,8,9018,36;7,9,9,17,9054,18;17,20,14,12,9072,42;14,16,19,12,9114,38;11,14,14,12,9152,28;6,8,5,21,9180,5;10,12,18,8,9185,36")
INDEX["SR20"] = ("PET sayRuiplotedkrKvnChg;wmc.H8fO\u2019b,MGSI34%U?", "12,14,16,8,9221,32;11,13,16,8,9253,32;11,13,16,8,9285,32;5,0,0,0,9317,0;10,12,13,11,9317,26;11,13,13,11,9343,26;10,13,18,11,9369,36;12,15,16,8,9405,32;12,14,13,11,9437,26;5,7,17,7,9463,17;12,14,18,11,9480,36;5,7,17,7,9516,17;12,14,13,11,9533,26;7,9,16,8,9559,32;11,13,13,11,9591,26;12,14,17,7,9617,34;11,13,17,7,9651,34;8,10,13,11,9685,26;12,15,16,8,9711,32;10,13,13,11,9743,26;12,14,13,11,9769,26;13,15,16,8,9795,32;12,14,17,7,9827,34;12,14,18,11,9861,36;5,7,16,11,9897,16;16,18,13,11,9913,39;19,21,13,11,9952,39;10,12,13,11,9991,26;5,7,5,19,10017,5;15,17,16,8,10022,48;11,13,16,8,10070,32;7,10,17,7,10102,34;16,18,16,8,10136,48;4,6,16,8,10184,16;12,14,17,7,10200,34;5,7,7,20,10234,7;18,20,16,8,10241,48;15,17,16,8,10289,48;11,13,16,8,10337,32;7,9,16,8,10369,32;11,13,16,8,10401,32;11,14,16,8,10433,32;17,19,16,8,10465,48;15,17,16,8,10513,48;9,11,16,8,10561,32")
INDEX["SR19"] = ("Trump: Ianwtsdel,bc;USiof.(AP)\u2019NEqh-gxR?", "11,13,16,7,10593,32;8,10,13,10,10625,26;12,14,13,10,10651,26;18,20,13,10,10677,39;12,14,18,10,10716,36;5,7,13,10,10752,13;5,0,0,0,10765,0;6,8,16,7,10765,16;11,13,13,10,10781,26;12,14,13,10,10807,26;15,17,13,10,10833,39;7,9,16,7,10872,32;9,11,13,10,10904,26;12,14,17,6,10930,34;11,13,13,10,10964,26;5,7,17,6,10990,17;5,7,7,19,11007,7;12,14,17,6,11014,34;9,11,13,10,11048,26;5,7,16,10,11074,16;14,16,16,7,11090,32;10,12,16,7,11122,32;5,7,17,6,11154,17;12,14,13,10,11171,26;7,10,17,6,11197,34;5,7,5,18,11231,5;6,8,20,7,11236,20;12,15,16,7,11256,32;12,14,16,7,11288,32;6,8,20,7,11320,20;3,6,16,7,11340,16;14,16,16,7,11356,32;11,13,16,7,11388,32;12,14,18,10,11420,36;12,14,17,6,11456,34;6,8,9,14,11490,9;12,14,18,10,11499,36;10,12,13,10,11535,26;12,14,16,7,11561,32;8,10,16,7,11593,32")
INDEX["SR16"] = ("Sources: Rt\u00b7UNwAPETlJazKMOgnhHid?", "9,11,14,6,11625,28;10,12,11,9,11653,22;10,12,11,9,11675,22;7,9,11,9,11697,22;8,10,11,9,11719,22;9,11,11,9,11741,22;8,10,11,9,11763,22;4,6,11,9,11785,11;4,0,0,0,11796,0;10,12,14,6,11796,28;6,8,13,7,11824,13;4,6,10,10,11837,10;12,14,14,6,11847,28;12,14,14,6,11875,28;13,15,11,9,11903,22;10,13,14,6,11925,28;10,12,14,6,11953,28;9,11,14,6,11981,28;9,11,14,6,12009,28;4,6,14,6,12037,14;4,8,18,6,12051,18;9,11,11,9,12069,22;8,10,11,9,12091,22;10,12,14,6,12113,28;15,17,14,6,12141,42;13,15,14,6,12183,28;10,12,15,9,12211,30;10,12,11,9,12241,22;10,12,14,6,12263,28;12,14,14,6,12291,28;4,6,14,6,12319,14;10,12,14,6,12333,28;7,9,14,6,12361,28")
INDEX["SR15"] = ("Al storiefmpngubhd21Nv06\u00b7Dawyc\u2014,I?", "10,12,12,7,12389,24;4,6,13,6,12413,13;4,0,0,0,12426,0;7,9,10,9,12426,20;5,8,12,7,12446,12;9,11,10,9,12458,20;6,8,10,9,12478,10;4,6,13,6,12488,13;8,10,10,9,12501,20;5,8,13,6,12521,13;14,16,10,9,12534,20;9,11,14,9,12554,28;9,11,10,9,12582,20;9,11,14,9,12602,28;9,11,10,9,12630,20;9,11,13,6,12650,26;9,11,13,6,12676,26;9,11,13,6,12702,26;9,11,12,7,12728,24;9,11,12,7,12752,24;11,13,12,7,12776,24;8,10,10,9,12800,20;9,11,12,7,12820,24;9,11,12,7,12844,24;4,6,8,11,12868,8;11,13,12,7,12876,24;8,10,10,9,12900,20;12,14,10,9,12920,20;8,10,14,9,12940,28;7,9,10,9,12968,20;15,17,7,12,12988,21;4,6,6,15,13009,6;5,7,12,7,13015,12;7,9,12,7,13027,24")
INDEX["SB22"] = ("123456?", "13,15,17,9,13051,34;13,15,17,9,13085,34;13,15,17,9,13119,34;13,15,17,9,13153,34;13,15,17,9,13187,34;13,15,17,9,13221,34;11,13,17,9,13255,34")


def _load_fonts():
    """Unpack _BLOB into per-table glyph dicts: char -> (adv, w, h, top, bits)."""
    blob = zlib.decompress(base64.b85decode("".join(_BLOB)))
    fonts = {}
    for name, (chars, metrics) in INDEX.items():
        glyphs = {}
        for ch, spec in zip(chars, metrics.split(";")):
            adv, w, h, top, off, n = (int(v) for v in spec.split(","))
            glyphs[ch] = (adv, w, h, top, blob[off:off + n])
        fonts[name] = glyphs
    return fonts


FONTS = _load_fonts()


def _glyph(table, ch):
    glyphs = FONTS[table]
    return glyphs[ch] if ch in glyphs else glyphs["?"]


def text_width(s, table):
    """How wide s sets in this table, in pixels."""
    total = 0
    for ch in s:
        total += _glyph(table, ch)[0]
    return total


def draw_text(cv, x, y, s, table, colour):
    """Set s with the top of its ascenders at y; hand back the pen's x."""
    for ch in s:
        adv, w, h, top, bits = _glyph(table, ch)
        if w and h:
            row_bytes = (w + 7) // 8
            ink_top = y + top - 1
            for row in range(h):
                for col in range(w):
                    byte = bits[row * row_bytes + col // 8]
                    if byte >> (7 - col % 8) & 1:
                        cv.set(x + col, ink_top + row, colour)
        x += adv
    return x


def wrap(s, table, max_width):
    """Greedy word wrap: the most words per line that still fit."""
    out = []
    line = ""
    for word in s.split():
        joined = word if not line else line + " " + word
        if text_width(joined, table) <= max_width:
            line = joined
        else:
            if line:
                out.append(line)
            line = word
    if line:
        out.append(line)
    return out


def draw_lines(cv, x, y, lines, table, colour, leading):
    """Set lines one under another; hand back the y below the last."""
    for line in lines:
        draw_text(cv, x, y, line, table, colour)
        y += leading
    return y


def fit_block(cv, x, y, width, text, table, leading, max_lines, colour=INK):
    """Wrap text into at most max_lines; refuse to draw it if it needs more."""
    lines = wrap(text, table, width)
    if len(lines) > max_lines:
        raise ValueError(
            f"{text!r} needs {len(lines)} lines, only {max_lines} fit")
    return draw_lines(cv, x, y, lines, table, colour, leading)


def draw_badge(cv, cx, cy, number):
    """A teal disc with a white number, marking one story."""
    cv.disc(cx, cy, 17, CHIP)
    label = str(number)
    half = text_width(label, "SB22") // 2
    draw_text(cv, cx - half, cy - 14, label, "SB22", WHITE)


# ---------------------------------------------------------------- page content

MASTHEAD = "THE WORLD TODAY"
DATE = "SATURDAY, 21 NOVEMBER 2026"
LEAD_KICKER = "CLIMATE  \u00b7  ANTALYA, T\u00dcRKIYE"
LEAD_HEAD = "COP31 runs into overtime as fossil fuels vanish from the draft deal"
LEAD_DECK = ("Negotiators from nearly 200 countries fail to agree a final text in "
             "Antalya; the slimmed-down draft drops every mention of fossil fuels.")
LEAD_SOURCE = "Sources: Reuters \u00b7 UN News \u00b7 AP"

STORIES = [
    {"n": 1, "kicker": "DENMARK  \u00b7  ESPIONAGE",
     "head": "Denmark foils \u201cRussian plot to kill rapper\u201d and expels envoy",
     "body": "PET says Russia plotted to kill rapper Kyivstoner in Copenhagen; two men charged.",
     "src": "Sources: PET \u00b7 Reuters \u00b7 Al Jazeera"},
    {"n": 2, "kicker": "STRAIT OF HORMUZ",
     "head": "Tanker hit by projectile catches fire off Oman",
     "body": "Hit 8 nautical miles north of Oman\u2019s Khasab; fire reported on board, no casualties.",
     "src": "Sources: UKMTO \u00b7 Reuters"},
    {"n": 3, "kicker": "UKRAINE  \u00b7  KYIV",
     "head": "Russian strikes kill eight in Kyiv as France seeks UN meeting",
     "body": "Missiles and drones hit Kyiv and energy sites; Estonia to shut its Russia crossings.",
     "src": "Sources: AP \u00b7 Reuters"},
    {"n": 4, "kicker": "INDIA  \u00b7  WEATHER",
     "head": "Cyclone Akvan weakens after landfall on India\u2019s east coast",
     "body": "The storm crosses the Odisha coast near Gopalpur, bringing heavy rain and disruption.",
     "src": "Sources: Jagran Josh \u00b7 The Hindu"},
]
WIDE = {"n": 5, "kicker": "MARKETS  \u00b7  TECH",
        "head": "Anthropic shares slide after record $81.3bn IPO debut",
        "body": "Shares pull back after the biggest IPO ever opened 34% higher; US stocks fall for a fifth straight session.",
        "src": "Source: Reuters"}
ALSO_ITEMS = [
    "Trump: Iran wants a deal, but terms are unacceptable; US sanctions four trustees.  (AP)",
    "India\u2019s NSE passes Nasdaq as the world\u2019s fifth-largest listed exchange.  (Reuters)",
]
FOOTER = ("All stories from reporting first published on 21 November 2026  \u00b7  "
          "Drawn entirely by code \u2014 no photography, no AI imagery")


def card_frame(cv, x, y, w, h):
    """A story card's outline and fill: a hairline shell, card colour inside."""
    cv.rounded(x, y, w, h, 10, HAIRLINE)
    cv.rounded(x + 1, y + 1, w - 2, h - 2, 9, CARD)


def paint_masthead(cv):
    """The teal band: paper name, date in gold, gold rule under it."""
    cv.rect(0, 0, WIDTH, 117, TEAL)
    name_w = text_width(MASTHEAD, "MAST")
    draw_text(cv, (WIDTH - name_w) // 2, 14, MASTHEAD, "MAST", WHITE)
    date_w = text_width(DATE, "SB19")
    draw_text(cv, (WIDTH - date_w) // 2, 82, DATE, "SB19", GOLD)
    cv.rect(0, 116, WIDTH, 5, GOLD)


def paint_lead(cv):
    """The lead story across the full width; hands back the y below it."""
    x = MARGIN
    top = 128
    draw_text(cv, x, top, LEAD_KICKER, "SB19", RUST)
    deck_top = fit_block(cv, x, top + 28, WIDTH - 2 * MARGIN, LEAD_HEAD,
                         "LEAD", leading=48, max_lines=2) + 4
    src_top = fit_block(cv, x, deck_top, WIDTH - 2 * MARGIN, LEAD_DECK,
                        "SR22", leading=29, max_lines=2, colour=BODY_INK) + 4
    draw_text(cv, x, src_top, LEAD_SOURCE, "SR16", SLATE)
    return src_top + 20


def paint_card(cv, x, y, w, h, story):
    """One grid card: badge and kicker, headline, short body, source line."""
    card_frame(cv, x, y, w, h)
    pad = 18
    ix = x + pad
    draw_badge(cv, ix + 17, y + 29, story["n"])
    draw_text(cv, ix + 44, y + 18, story["kicker"], "SB19", RUST)
    body_top = fit_block(cv, ix, y + 52, w - 2 * pad, story["head"],
                         "SB25", leading=28, max_lines=2) + 3
    fit_block(cv, ix, body_top, w - 2 * pad, story["body"],
              "SR20", leading=24, max_lines=3, colour=BODY_INK)
    draw_text(cv, ix, y + h - 22, story["src"], "SR16", SLATE)
    return y + h


def paint_wide(cv, x, y, w, h, story):
    """A full-width strip: badge on the left, headline and body on the right."""
    card_frame(cv, x, y, w, h)
    pad = 18
    draw_badge(cv, x + pad + 17, y + h // 2, story["n"])
    tx = x + pad + 52
    tw = w - pad - 52 - pad
    draw_text(cv, tx, y + 10, story["kicker"], "SB19", RUST)
    src_w = text_width(story["src"], "SR16")
    draw_text(cv, x + w - pad - src_w, y + 10, story["src"], "SR16", SLATE)
    if text_width(story["head"], "SB25") > tw:
        raise ValueError(f"wide headline too long: {story['head']!r}")
    draw_text(cv, tx, y + 34, story["head"], "SB25", INK)
    fit_block(cv, tx, y + 61, tw, story["body"],
              "SR20", leading=24, max_lines=2, colour=BODY_INK)
    return y + h


def paint_also(cv, y, h):
    """The dark strip at the bottom: two short items that missed the grid."""
    cv.rect(0, y, WIDTH, h, TEAL_DARK)
    draw_text(cv, MARGIN, y + 8, "ALSO TODAY", "SB19", GOLD)
    col_w = (WIDTH - 2 * MARGIN - 30) // 2
    for i, item in enumerate(ALSO_ITEMS):
        col_x = MARGIN + i * (col_w + 30)
        fit_block(cv, col_x, y + 32, col_w, item, "SR19",
                  leading=23, max_lines=2, colour=PALE)
    return y + h


def paint_page():
    """Lay the whole front page out, top to bottom, and hand back the canvas."""
    cv = Canvas(WIDTH, HEIGHT, PAPER)

    paint_masthead(cv)
    below_lead = paint_lead(cv)
    cv.rect(MARGIN, below_lead, WIDTH - 2 * MARGIN, 2, HAIRLINE)

    grid_top = below_lead + 12
    card_w = (WIDTH - 2 * MARGIN - 20) // 2
    card_h = 210
    col_step = card_w + 20
    row_step = card_h + 10
    for pos, story in enumerate(STORIES):
        col = pos % 2
        row = pos // 2
        paint_card(cv, MARGIN + col * col_step,
                   grid_top + row * row_step, card_w, card_h, story)

    wide_top = grid_top + 2 * card_h + 10 + 12
    paint_wide(cv, MARGIN, wide_top, WIDTH - 2 * MARGIN, 116, WIDE)

    also_bottom = paint_also(cv, wide_top + 116 + 10, 80)

    foot_w = text_width(FOOTER, "SR15")
    draw_text(cv, (WIDTH - foot_w) // 2, HEIGHT - 21, FOOTER, "SR15", SLATE)
    if also_bottom > HEIGHT - 26:
        raise ValueError(f"layout overflow: bottom band ends at {also_bottom}")
    return cv


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)

    cv = paint_page()
    png = encode_png(WIDTH, HEIGHT, bytes(cv.px))
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(png)
    print("wrote", path, len(png), "bytes")


if __name__ == "__main__":
    main()
