"""
Plural rules generated from the CLDR data
"""
import decimal
import typing as t


D = decimal.Decimal
TNumber = int | float | D
TRangeList = t.Iterable[tuple[int, int]]


def plural_am(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(0, 0)]) or IN(n, [(1, 1)]):
        return "one"


def plural_as(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(0, 0)]) or IN(n, [(1, 1)]):
        return "one"


def plural_bn(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(0, 0)]) or IN(n, [(1, 1)]):
        return "one"


def plural_doi(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(0, 0)]) or IN(n, [(1, 1)]):
        return "one"


def plural_fa(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(0, 0)]) or IN(n, [(1, 1)]):
        return "one"


def plural_gu(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(0, 0)]) or IN(n, [(1, 1)]):
        return "one"


def plural_hi(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(0, 0)]) or IN(n, [(1, 1)]):
        return "one"


def plural_kn(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(0, 0)]) or IN(n, [(1, 1)]):
        return "one"


def plural_pcm(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(0, 0)]) or IN(n, [(1, 1)]):
        return "one"


def plural_zu(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(0, 0)]) or IN(n, [(1, 1)]):
        return "one"


def plural_ff(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(0, 0), (1, 1)]):
        return "one"


def plural_hy(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(0, 0), (1, 1)]):
        return "one"


def plural_kab(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(0, 0), (1, 1)]):
        return "one"


def plural_ast(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_de(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_en(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_et(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_fi(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_fy(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_gl(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_ia(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_io(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_ji(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_lij(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_nl(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_sc(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_scn(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_sv(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_sw(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_ur(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_yi(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_si(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(0, 0), (1, 1)]) or (IN(i, [(0, 0)]) and IN(f, [(1, 1)])):
        return "one"


def plural_ak(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(0, 1)]):
        return "one"


def plural_bho(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(0, 1)]):
        return "one"


def plural_guw(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(0, 1)]):
        return "one"


def plural_ln(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(0, 1)]):
        return "one"


def plural_mg(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(0, 1)]):
        return "one"


def plural_nso(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(0, 1)]):
        return "one"


def plural_pa(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(0, 1)]):
        return "one"


def plural_ti(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(0, 1)]):
        return "one"


def plural_wa(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(0, 1)]):
        return "one"


def plural_tzm(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(0, 1)]) or IN(n, [(11, 99)]):
        return "one"


def plural_af(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_an(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_asa(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_az(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_bal(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_bem(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_bez(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_bg(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_brx(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_ce(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_cgg(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_chr(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_ckb(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_dv(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_ee(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_el(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_eo(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_eu(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_fo(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_fur(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_gsw(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_ha(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_haw(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_hu(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_jgo(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_jmc(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_ka(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_kaj(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_kcg(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_kk(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_kkj(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_kl(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_ks(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_ksb(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_ku(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_ky(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_lb(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_lg(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_mas(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_mgo(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_ml(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_mn(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_mr(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_nah(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_nb(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_nd(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_ne(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_nn(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_nnh(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_no(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_nr(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_ny(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_nyn(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_om(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_or(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_os(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_pap(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_ps(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_rm(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_rof(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_rwk(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_saq(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_sd(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_sdh(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_seh(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_sn(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_so(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_sq(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_ss(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_ssy(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_st(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_syr(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_ta(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_te(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_teo(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_tig(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_tk(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_tn(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_tr(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_ts(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_ug(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_uz(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_ve(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_vo(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_vun(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_wae(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_xh(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_xog(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"


def plural_da(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]) or ((not IN(t, [(0, 0)])) and IN(i, [(0, 0), (1, 1)])):
        return "one"


def plural_is(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (
        (IN(t, [(0, 0)]) and IN(MOD(i, 10), [(1, 1)]))
        and (not IN(MOD(i, 100), [(11, 11)]))
    ) or (IN(MOD(t, 10), [(1, 1)]) and (not IN(MOD(t, 100), [(11, 11)]))):
        return "one"


def plural_mk(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (
        (IN(v, [(0, 0)]) and IN(MOD(i, 10), [(1, 1)]))
        and (not IN(MOD(i, 100), [(11, 11)]))
    ) or (IN(MOD(f, 10), [(1, 1)]) and (not IN(MOD(f, 100), [(11, 11)]))):
        return "one"


def plural_ceb(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (
        (IN(v, [(0, 0)]) and IN(i, [(1, 1), (2, 2), (3, 3)]))
        or (IN(v, [(0, 0)]) and (not IN(MOD(i, 10), [(4, 4), (6, 6), (9, 9)])))
    ) or ((not IN(v, [(0, 0)])) and (not IN(MOD(f, 10), [(4, 4), (6, 6), (9, 9)]))):
        return "one"


def plural_fil(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (
        (IN(v, [(0, 0)]) and IN(i, [(1, 1), (2, 2), (3, 3)]))
        or (IN(v, [(0, 0)]) and (not IN(MOD(i, 10), [(4, 4), (6, 6), (9, 9)])))
    ) or ((not IN(v, [(0, 0)])) and (not IN(MOD(f, 10), [(4, 4), (6, 6), (9, 9)]))):
        return "one"


def plural_tl(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (
        (IN(v, [(0, 0)]) and IN(i, [(1, 1), (2, 2), (3, 3)]))
        or (IN(v, [(0, 0)]) and (not IN(MOD(i, 10), [(4, 4), (6, 6), (9, 9)])))
    ) or ((not IN(v, [(0, 0)])) and (not IN(MOD(f, 10), [(4, 4), (6, 6), (9, 9)]))):
        return "one"


def plural_lv(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (
        (IN(MOD(n, 10), [(1, 1)]) and (not IN(MOD(n, 100), [(11, 11)])))
        or (
            (IN(v, [(2, 2)]) and IN(MOD(f, 10), [(1, 1)]))
            and (not IN(MOD(f, 100), [(11, 11)]))
        )
    ) or ((not IN(v, [(2, 2)])) and IN(MOD(f, 10), [(1, 1)])):
        return "one"
    if (IN(MOD(n, 10), [(0, 0)]) or IN(MOD(n, 100), [(11, 19)])) or (
        IN(v, [(2, 2)]) and IN(MOD(f, 100), [(11, 19)])
    ):
        return "zero"


def plural_prg(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (
        (IN(MOD(n, 10), [(1, 1)]) and (not IN(MOD(n, 100), [(11, 11)])))
        or (
            (IN(v, [(2, 2)]) and IN(MOD(f, 10), [(1, 1)]))
            and (not IN(MOD(f, 100), [(11, 11)]))
        )
    ) or ((not IN(v, [(2, 2)])) and IN(MOD(f, 10), [(1, 1)])):
        return "one"
    if (IN(MOD(n, 10), [(0, 0)]) or IN(MOD(n, 100), [(11, 19)])) or (
        IN(v, [(2, 2)]) and IN(MOD(f, 100), [(11, 19)])
    ):
        return "zero"


def plural_lag(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(0, 0), (1, 1)]) and (not IN(n, [(0, 0)])):
        return "one"
    if IN(n, [(0, 0)]):
        return "zero"


def plural_ksh(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"
    if IN(n, [(0, 0)]):
        return "zero"


def plural_he(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (IN(i, [(1, 1)]) and IN(v, [(0, 0)])) or (
        IN(i, [(0, 0)]) and (not IN(v, [(0, 0)]))
    ):
        return "one"
    if IN(i, [(2, 2)]) and IN(v, [(0, 0)]):
        return "two"


def plural_iw(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (IN(i, [(1, 1)]) and IN(v, [(0, 0)])) or (
        IN(i, [(0, 0)]) and (not IN(v, [(0, 0)]))
    ):
        return "one"
    if IN(i, [(2, 2)]) and IN(v, [(0, 0)]):
        return "two"


def plural_iu(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"
    if IN(n, [(2, 2)]):
        return "two"


def plural_naq(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"
    if IN(n, [(2, 2)]):
        return "two"


def plural_sat(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"
    if IN(n, [(2, 2)]):
        return "two"


def plural_se(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"
    if IN(n, [(2, 2)]):
        return "two"


def plural_sma(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"
    if IN(n, [(2, 2)]):
        return "two"


def plural_smi(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"
    if IN(n, [(2, 2)]):
        return "two"


def plural_smj(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"
    if IN(n, [(2, 2)]):
        return "two"


def plural_smn(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"
    if IN(n, [(2, 2)]):
        return "two"


def plural_sms(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(1, 1)]):
        return "one"
    if IN(n, [(2, 2)]):
        return "two"


def plural_shi(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(2, 10)]):
        return "few"
    if IN(i, [(0, 0)]) or IN(n, [(1, 1)]):
        return "one"


def plural_mo(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if ((not IN(v, [(0, 0)])) or IN(n, [(0, 0)])) or (
        (not IN(n, [(1, 1)])) and IN(MOD(n, 100), [(1, 19)])
    ):
        return "few"
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_ro(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if ((not IN(v, [(0, 0)])) or IN(n, [(0, 0)])) or (
        (not IN(n, [(1, 1)])) and IN(MOD(n, 100), [(1, 19)])
    ):
        return "few"
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_bs(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (
        (IN(v, [(0, 0)]) and IN(MOD(i, 10), [(2, 4)]))
        and (not IN(MOD(i, 100), [(12, 14)]))
    ) or (IN(MOD(f, 10), [(2, 4)]) and (not IN(MOD(f, 100), [(12, 14)]))):
        return "few"
    if (
        (IN(v, [(0, 0)]) and IN(MOD(i, 10), [(1, 1)]))
        and (not IN(MOD(i, 100), [(11, 11)]))
    ) or (IN(MOD(f, 10), [(1, 1)]) and (not IN(MOD(f, 100), [(11, 11)]))):
        return "one"


def plural_hr(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (
        (IN(v, [(0, 0)]) and IN(MOD(i, 10), [(2, 4)]))
        and (not IN(MOD(i, 100), [(12, 14)]))
    ) or (IN(MOD(f, 10), [(2, 4)]) and (not IN(MOD(f, 100), [(12, 14)]))):
        return "few"
    if (
        (IN(v, [(0, 0)]) and IN(MOD(i, 10), [(1, 1)]))
        and (not IN(MOD(i, 100), [(11, 11)]))
    ) or (IN(MOD(f, 10), [(1, 1)]) and (not IN(MOD(f, 100), [(11, 11)]))):
        return "one"


def plural_sh(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (
        (IN(v, [(0, 0)]) and IN(MOD(i, 10), [(2, 4)]))
        and (not IN(MOD(i, 100), [(12, 14)]))
    ) or (IN(MOD(f, 10), [(2, 4)]) and (not IN(MOD(f, 100), [(12, 14)]))):
        return "few"
    if (
        (IN(v, [(0, 0)]) and IN(MOD(i, 10), [(1, 1)]))
        and (not IN(MOD(i, 100), [(11, 11)]))
    ) or (IN(MOD(f, 10), [(1, 1)]) and (not IN(MOD(f, 100), [(11, 11)]))):
        return "one"


def plural_sr(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (
        (IN(v, [(0, 0)]) and IN(MOD(i, 10), [(2, 4)]))
        and (not IN(MOD(i, 100), [(12, 14)]))
    ) or (IN(MOD(f, 10), [(2, 4)]) and (not IN(MOD(f, 100), [(12, 14)]))):
        return "few"
    if (
        (IN(v, [(0, 0)]) and IN(MOD(i, 10), [(1, 1)]))
        and (not IN(MOD(i, 100), [(11, 11)]))
    ) or (IN(MOD(f, 10), [(1, 1)]) and (not IN(MOD(f, 100), [(11, 11)]))):
        return "one"


def plural_fr(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (
        ((IN(e, [(0, 0)]) and (not IN(i, [(0, 0)]))) and IN(MOD(i, 1000000), [(0, 0)]))
        and IN(v, [(0, 0)])
    ) or (not IN(e, [(0, 5)])):
        return "many"
    if IN(i, [(0, 0), (1, 1)]):
        return "one"


def plural_pt(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (
        ((IN(e, [(0, 0)]) and (not IN(i, [(0, 0)]))) and IN(MOD(i, 1000000), [(0, 0)]))
        and IN(v, [(0, 0)])
    ) or (not IN(e, [(0, 5)])):
        return "many"
    if IN(i, [(0, 1)]):
        return "one"


def plural_ca(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (
        ((IN(e, [(0, 0)]) and (not IN(i, [(0, 0)]))) and IN(MOD(i, 1000000), [(0, 0)]))
        and IN(v, [(0, 0)])
    ) or (not IN(e, [(0, 5)])):
        return "many"
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_it(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (
        ((IN(e, [(0, 0)]) and (not IN(i, [(0, 0)]))) and IN(MOD(i, 1000000), [(0, 0)]))
        and IN(v, [(0, 0)])
    ) or (not IN(e, [(0, 5)])):
        return "many"
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_pt_PT(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (
        ((IN(e, [(0, 0)]) and (not IN(i, [(0, 0)]))) and IN(MOD(i, 1000000), [(0, 0)]))
        and IN(v, [(0, 0)])
    ) or (not IN(e, [(0, 5)])):
        return "many"
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_vec(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (
        ((IN(e, [(0, 0)]) and (not IN(i, [(0, 0)]))) and IN(MOD(i, 1000000), [(0, 0)]))
        and IN(v, [(0, 0)])
    ) or (not IN(e, [(0, 5)])):
        return "many"
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_es(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (
        ((IN(e, [(0, 0)]) and (not IN(i, [(0, 0)]))) and IN(MOD(i, 1000000), [(0, 0)]))
        and IN(v, [(0, 0)])
    ) or (not IN(e, [(0, 5)])):
        return "many"
    if IN(n, [(1, 1)]):
        return "one"


def plural_gd(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(3, 10), (13, 19)]):
        return "few"
    if IN(n, [(1, 1), (11, 11)]):
        return "one"
    if IN(n, [(2, 2), (12, 12)]):
        return "two"


def plural_sl(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (IN(v, [(0, 0)]) and IN(MOD(i, 100), [(3, 4)])) or (not IN(v, [(0, 0)])):
        return "few"
    if IN(v, [(0, 0)]) and IN(MOD(i, 100), [(1, 1)]):
        return "one"
    if IN(v, [(0, 0)]) and IN(MOD(i, 100), [(2, 2)]):
        return "two"


def plural_dsb(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (IN(v, [(0, 0)]) and IN(MOD(i, 100), [(3, 4)])) or IN(MOD(f, 100), [(3, 4)]):
        return "few"
    if (IN(v, [(0, 0)]) and IN(MOD(i, 100), [(1, 1)])) or IN(MOD(f, 100), [(1, 1)]):
        return "one"
    if (IN(v, [(0, 0)]) and IN(MOD(i, 100), [(2, 2)])) or IN(MOD(f, 100), [(2, 2)]):
        return "two"


def plural_hsb(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (IN(v, [(0, 0)]) and IN(MOD(i, 100), [(3, 4)])) or IN(MOD(f, 100), [(3, 4)]):
        return "few"
    if (IN(v, [(0, 0)]) and IN(MOD(i, 100), [(1, 1)])) or IN(MOD(f, 100), [(1, 1)]):
        return "one"
    if (IN(v, [(0, 0)]) and IN(MOD(i, 100), [(2, 2)])) or IN(MOD(f, 100), [(2, 2)]):
        return "two"


def plural_cs(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(2, 4)]) and IN(v, [(0, 0)]):
        return "few"
    if not IN(v, [(0, 0)]):
        return "many"
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_sk(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(i, [(2, 4)]) and IN(v, [(0, 0)]):
        return "few"
    if not IN(v, [(0, 0)]):
        return "many"
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_pl(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (IN(v, [(0, 0)]) and IN(MOD(i, 10), [(2, 4)])) and (
        not IN(MOD(i, 100), [(12, 14)])
    ):
        return "few"
    if (
        ((IN(v, [(0, 0)]) and (not IN(i, [(1, 1)]))) and IN(MOD(i, 10), [(0, 1)]))
        or (IN(v, [(0, 0)]) and IN(MOD(i, 10), [(5, 9)]))
    ) or (IN(v, [(0, 0)]) and IN(MOD(i, 100), [(12, 14)])):
        return "many"
    if IN(i, [(1, 1)]) and IN(v, [(0, 0)]):
        return "one"


def plural_be(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(MOD(n, 10), [(2, 4)]) and (not IN(MOD(n, 100), [(12, 14)])):
        return "few"
    if (IN(MOD(n, 10), [(0, 0)]) or IN(MOD(n, 10), [(5, 9)])) or IN(
        MOD(n, 100), [(11, 14)]
    ):
        return "many"
    if IN(MOD(n, 10), [(1, 1)]) and (not IN(MOD(n, 100), [(11, 11)])):
        return "one"


def plural_lt(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(MOD(n, 10), [(2, 9)]) and (not IN(MOD(n, 100), [(11, 19)])):
        return "few"
    if not IN(f, [(0, 0)]):
        return "many"
    if IN(MOD(n, 10), [(1, 1)]) and (not IN(MOD(n, 100), [(11, 19)])):
        return "one"


def plural_ru(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (IN(v, [(0, 0)]) and IN(MOD(i, 10), [(2, 4)])) and (
        not IN(MOD(i, 100), [(12, 14)])
    ):
        return "few"
    if (
        (IN(v, [(0, 0)]) and IN(MOD(i, 10), [(0, 0)]))
        or (IN(v, [(0, 0)]) and IN(MOD(i, 10), [(5, 9)]))
    ) or (IN(v, [(0, 0)]) and IN(MOD(i, 100), [(11, 14)])):
        return "many"
    if (IN(v, [(0, 0)]) and IN(MOD(i, 10), [(1, 1)])) and (
        not IN(MOD(i, 100), [(11, 11)])
    ):
        return "one"


def plural_uk(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if (IN(v, [(0, 0)]) and IN(MOD(i, 10), [(2, 4)])) and (
        not IN(MOD(i, 100), [(12, 14)])
    ):
        return "few"
    if (
        (IN(v, [(0, 0)]) and IN(MOD(i, 10), [(0, 0)]))
        or (IN(v, [(0, 0)]) and IN(MOD(i, 10), [(5, 9)]))
    ) or (IN(v, [(0, 0)]) and IN(MOD(i, 100), [(11, 14)])):
        return "many"
    if (IN(v, [(0, 0)]) and IN(MOD(i, 10), [(1, 1)])) and (
        not IN(MOD(i, 100), [(11, 11)])
    ):
        return "one"


def plural_br(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(MOD(n, 10), [(3, 4), (9, 9)]) and (
        not IN(MOD(n, 100), [(10, 19), (70, 79), (90, 99)])
    ):
        return "few"
    if (not IN(n, [(0, 0)])) and IN(MOD(n, 1000000), [(0, 0)]):
        return "many"
    if IN(MOD(n, 10), [(1, 1)]) and (
        not IN(MOD(n, 100), [(11, 11), (71, 71), (91, 91)])
    ):
        return "one"
    if IN(MOD(n, 10), [(2, 2)]) and (
        not IN(MOD(n, 100), [(12, 12), (72, 72), (92, 92)])
    ):
        return "two"


def plural_mt(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(0, 0)]) or IN(MOD(n, 100), [(3, 10)]):
        return "few"
    if IN(MOD(n, 100), [(11, 19)]):
        return "many"
    if IN(n, [(1, 1)]):
        return "one"
    if IN(n, [(2, 2)]):
        return "two"


def plural_ga(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(3, 6)]):
        return "few"
    if IN(n, [(7, 10)]):
        return "many"
    if IN(n, [(1, 1)]):
        return "one"
    if IN(n, [(2, 2)]):
        return "two"


def plural_gv(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(v, [(0, 0)]) and IN(
        MOD(i, 100), [(0, 0), (20, 20), (40, 40), (60, 60), (80, 80)]
    ):
        return "few"
    if not IN(v, [(0, 0)]):
        return "many"
    if IN(v, [(0, 0)]) and IN(MOD(i, 10), [(1, 1)]):
        return "one"
    if IN(v, [(0, 0)]) and IN(MOD(i, 10), [(2, 2)]):
        return "two"


def plural_kw(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(MOD(n, 100), [(3, 3), (23, 23), (43, 43), (63, 63), (83, 83)]):
        return "few"
    if (not IN(n, [(1, 1)])) and IN(
        MOD(n, 100), [(1, 1), (21, 21), (41, 41), (61, 61), (81, 81)]
    ):
        return "many"
    if IN(n, [(1, 1)]):
        return "one"
    if (
        IN(MOD(n, 100), [(2, 2), (22, 22), (42, 42), (62, 62), (82, 82)])
        or (
            IN(MOD(n, 1000), [(0, 0)])
            and IN(
                MOD(n, 100000),
                [(1000, 20000), (40000, 40000), (60000, 60000), (80000, 80000)],
            )
        )
    ) or ((not IN(n, [(0, 0)])) and IN(MOD(n, 1000000), [(100000, 100000)])):
        return "two"
    if IN(n, [(0, 0)]):
        return "zero"


def plural_ar(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(MOD(n, 100), [(3, 10)]):
        return "few"
    if IN(MOD(n, 100), [(11, 99)]):
        return "many"
    if IN(n, [(1, 1)]):
        return "one"
    if IN(n, [(2, 2)]):
        return "two"
    if IN(n, [(0, 0)]):
        return "zero"


def plural_ars(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(MOD(n, 100), [(3, 10)]):
        return "few"
    if IN(MOD(n, 100), [(11, 99)]):
        return "many"
    if IN(n, [(1, 1)]):
        return "one"
    if IN(n, [(2, 2)]):
        return "two"
    if IN(n, [(0, 0)]):
        return "zero"


def plural_cy(count: TNumber) -> str | None:
    n, i, v, f, t, e = extract_operands(count)
    if IN(n, [(3, 3)]):
        return "few"
    if IN(n, [(6, 6)]):
        return "many"
    if IN(n, [(1, 1)]):
        return "one"
    if IN(n, [(2, 2)]):
        return "two"
    if IN(n, [(0, 0)]):
        return "zero"


# The following code was extracted from the Babel project
# https://github.com/python-babel/babel
# Redistribuded under the BSD License
#
# Copyright (c) 2013-2023 by the Babel Team
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#  1. Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#  2. Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in
#     the documentation and/or other materials provided with the
#     distribution.
#  3. Neither the name of the copyright holder nor the names of its
#     contributors may be used to endorse or promote products derived
#     from this software without specific prior written permission.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


def extract_operands(
    count: TNumber,
) -> (
    tuple[int | D, int, int, int, int, t.Literal[0]]
):
    """Extract operands from a decimal, a float or an int, according to [CLDR rules][cldr_rules].

    The result is an 8-tuple (n, i, v, f, t, e), where those symbols are as follows:

    ====== ===============================================================
    Symbol Value
    ------ ---------------------------------------------------------------
    n      absolute value of the source number (integer and decimals).
    i      integer digits of n.
    v      number of visible fraction digits in n, with trailing zeros.
    f      visible fractional digits in n, with trailing zeros.
    t      visible fractional digits in n, without trailing zeros.
    e      compact decimal exponent value: exponent of the power of 10 used in compact decimal formatting.
    ====== ===============================================================

    [cldr_rules]: https://www.unicode.org/reports/tr35/tr35-61/tr35-numbers.html#Operands

    """
    n = abs(count)
    i = int(n)
    if isinstance(n, float):
        if i == n:
            n = i
        else:
            # Cast the `float` to a number via the string representation.
            n = D(str(n))

    if isinstance(n, D):
        dec_tuple = n.as_tuple()
        exp = dec_tuple.exponent
        if isinstance(exp, int) and exp < 0:
            fraction_digits = dec_tuple.digits[exp:]
        else:
            fraction_digits = ()
        trailing = "".join(str(d) for d in fraction_digits)
        no_trailing = trailing.rstrip("0")
        v = len(trailing)
        f = int(trailing or 0)
        t = int(no_trailing or 0)
    else:
        v = f = t = 0

    e = 0  # not supported
    return n, i, v, f, t, e


def in_range_list(num: TNumber, range_list: TRangeList) -> bool:
    """Integer range list test.  This is the callback for the "in" operator
    of the UTS #35 pluralization rule language:

    >>> in_range_list(1, [(1, 3)])
    True
    >>> in_range_list(3, [(1, 3)])
    True
    >>> in_range_list(3, [(1, 3), (5, 8)])
    True
    >>> in_range_list(1.2, [(1, 4)])
    False
    >>> in_range_list(10, [(1, 4)])
    False
    >>> in_range_list(10, [(1, 4), (6, 8)])
    False
    """
    return num == int(num) and within_range_list(num, range_list)


def within_range_list(num: TNumber, range_list: TRangeList) -> bool:
    """Float range test.  This is the callback for the "within" operator
    of the UTS #35 pluralization rule language:

    >>> within_range_list(1, [(1, 3)])
    True
    >>> within_range_list(1.0, [(1, 3)])
    True
    >>> within_range_list(1.2, [(1, 4)])
    True
    >>> within_range_list(8.8, [(1, 4), (7, 15)])
    True
    >>> within_range_list(10, [(1, 4)])
    False
    >>> within_range_list(10.5, [(1, 4), (20, 30)])
    False
    """
    return any(num >= min_ and num <= max_ for min_, max_ in range_list)


def cldr_modulo(a: TNumber, b: int) -> TNumber:
    """Javaish modulo.  This modulo operator returns the value with the sign
    of the dividend rather than the divisor like Python does:

    >>> cldr_modulo(-3, 5)
    -3
    >>> cldr_modulo(-3, -5)
    -3
    >>> cldr_modulo(3, 5)
    3
    """
    reverse = 0
    if a < 0:
        a *= -1
        reverse = 1
    if b < 0:
        b *= -1
    rv = a % b
    if reverse:
        rv *= -1
    return rv


IN = in_range_list
WITHIN = within_range_list
MOD = cldr_modulo
