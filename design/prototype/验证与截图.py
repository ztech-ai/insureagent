#!/usr/bin/env python3
"""Verify the local prototype interactions and export screenshots with Chromium."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'insurance-mobile.html'
SCREENS = [('today','今天'),('record','口述记录'),('confirm','确认归档'),('customer','客户详情'),('insight','建议与计划'),('tasks','跟进安排'),('customers','客户列表'),('assistant','客户助手'),('me','我的与套餐'),('privacy','隐私与数据')]

def wrapper(fragment):
    return '<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><style>body{margin:0;padding:0;background:light-dark(#fff,#111916)}</style></head><body>' + fragment + '</body></html>'

def main():
    fragment = SOURCE.read_text()
    assert SOURCE.stat().st_size < 1024 * 1024
    assert all(x not in fragment.lower() for x in ['<html', '<body', '<!doctype', 'fetch(', 'xmlhttprequest', 'websocket'])
    errors, checks = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width':736,'height':1100}, device_scale_factor=1)
        page.on('pageerror', lambda e: errors.append(str(e)))
        def reset():
            page.set_content(wrapper(fragment))
        def screen(name):
            page.locator('#zk-screen-picker').select_option(name)
        reset()
        page.locator('[data-action=record]').first.click()
        page.locator('[data-action=pause]').click()
        assert page.get_by_text('示例录音已暂停').count() == 1
        page.locator('[data-action=finish-record]').click()
        assert page.locator('[data-action=archive]').is_disabled()
        assert page.locator('input[data-fact]:checked').count() == 0
        page.locator('input[name=zk-person][value=existing]').check()
        assert page.locator('[data-action=archive]').text_content() == '仅归档到所选客户'
        page.locator('input[data-fact=need]').check()
        page.locator('[data-action=archive]').click()
        assert '1 项事实已确认' in page.locator('.zk-notice').text_content()
        page.locator('[data-go=insight]').click()
        page.locator('[data-go=task-edit]').click()
        page.locator('#zk-task-title').fill('核实家庭已有保障')
        page.locator('[data-action=save-task]').click()
        assert page.get_by_text('陈敏 · 核实家庭已有保障',exact=True).count() == 1
        page.locator('[data-action=complete]').click()
        page.locator('input[name=zk-outcome][value=已联系]').check()
        page.locator('[data-action=save-outcome]').click()
        assert page.get_by_text('联系结果：已联系',exact=True).count() == 1
        page.locator('[data-action=complete-zhou]').click()
        page.locator('input[name=zk-outcome][value=未接通]').check()
        page.locator('[data-action=save-outcome]').click()
        assert page.get_by_text('联系结果：未接通',exact=True).count() == 1
        assert page.get_by_text('陈敏 · 核实家庭已有保障',exact=True).count() == 1
        checks.append('口述、暂停、同名确认、事实选择、归档、创建跟进和联系结果')

        reset(); screen('customer')
        page.locator('[data-go=contact]').click()
        page.locator('input[name=zk-contact][value=never]').check()
        page.locator('[data-action=save-contact]').click()
        page.locator('[data-go=insight]').click()
        assert page.locator('[data-go=task-edit]').count() == 0
        checks.append('拒绝联系后阻止采纳主动经营建议')

        reset(); screen('assistant')
        page.locator('[data-action=edit-source]').click()
        corrected='客户尚未约定联系时间，需要先确认沟通意愿。'
        page.locator('#zk-edit-text').fill(corrected)
        page.locator('[data-action=save-correction]').click()
        page.locator('[data-go=insight]').click()
        assert page.locator('[data-go=task-edit]').count() == 0
        page.locator('[data-action=regenerate]').click()
        assert page.locator('[data-go=task-edit]').count() == 0
        page.locator('[data-action=source]').click()
        assert page.locator('.zk-quote').text_content() == corrected
        checks.append('更正来源后旧建议失效，原文保持更正内容')

        for scenario in ['offline','permission','quota','partial']:
            reset()
            page.locator('#zk-scenario-picker').select_option(scenario)
            if scenario in ['offline','quota']:
                page.locator('[data-action=finish-record]').click()
                assert page.get_by_role('heading',name='本机草稿').count() == 1
            elif scenario == 'permission':
                assert page.locator('#zk-record-text').count() == 1
                page.locator('[data-action=finish-record]').click()
                assert page.get_by_role('heading',name='确认归档').count() == 1
            else:
                assert page.get_by_text('文字已保存，信息整理暂未完成。',exact=False).count() == 1
                page.locator('[data-action=retry]').click()
                assert page.get_by_role('heading',name='确认归档').count() == 1
        checks.append('离线、拒绝录音权限、额度用尽、部分成功的恢复路径')

        reset(); screen('privacy')
        page.locator('[data-go=delete]').click()
        assert page.locator('[data-action=submit-delete]').is_disabled()
        page.locator('#zk-delete-check').check()
        page.locator('[data-action=submit-delete]').click()
        assert page.get_by_role('heading',name='正在清理相关资料').count() == 1
        assert page.locator('[data-action=submit-delete]').count() == 0
        checks.append('删除明确确认、提交后进度展示')
        reset(); screen('customers')
        page.locator('#zk-search').fill('陈敏')
        assert page.locator('#zk-customer-list .zk-list-button').count() == 2
        page.locator('#zk-search').fill('没有这位客户')
        assert page.get_by_text('没有找到匹配客户',exact=False).count() == 1
        checks.append('客户搜索和空结果')

        for width in [320,390,736]:
            page.set_viewport_size({'width':width,'height':1100})
            reset()
            for route,_ in SCREENS:
                screen(route)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), (width,route)
                overflow = page.locator('.zk-phone').evaluate('el => el.scrollWidth > el.clientWidth + 1')
                assert not overflow, (width,route,'phone overflow')
        checks.append('10 个主页面在 320、390、736 宽度无横向溢出')
        page.set_viewport_size({'width':736,'height':1100})
        page.emulate_media(color_scheme='dark')
        reset();page.locator('.zk-phone').screenshot(path=str(ROOT/'深色首页.png'))
        page.emulate_media(color_scheme='light')
        screenshots={}
        for index,(route,label) in enumerate(SCREENS,1):
            reset();screen(route)
            page.locator('.zk-phone').screenshot(path=str(ROOT/f'{index:02d}_{label}.png'))
            screenshots[route]=page.locator('.zk-phone').evaluate('el => el.outerHTML')
        style=page.locator('style').all_text_contents()[-1]
        # Layout existing UI DOM as two static review boards; no external resources.
        boards=[('核心流程总览.png','保知伴 AI · 核心使用流程',SCREENS[:6],3),('客户与设置总览.png','保知伴 AI · 客户、助手与设置',SCREENS[6:],2)]
        for filename,title,items,cols in boards:
            html='<div id="insurance-mobile-prototype"><div class="board-title">'+title+'</div><div class="board-subtitle">移动端 UI 原型 · 虚构示例 · 390 px 设计基准</div><div class="board-grid">'
            for index,(route,label) in enumerate(items,1):
                html+='<section><div class="board-label">'+f'{index:02d}　{label}'+'</div>'+screenshots[route].replace('id="zk-app"','')+'</section>'
            html+='</div></div><style>'+style+'</style><style>body{background:#e9ede6;color-scheme:light;padding:36px;}#insurance-mobile-prototype .board-title{font-size:32px;font-weight:650;letter-spacing:-1px;}#insurance-mobile-prototype .board-subtitle{font-size:15px;margin:10px 0 24px;color:#627269;}#insurance-mobile-prototype .board-grid{display:grid;grid-template-columns:repeat('+str(cols)+',390px);gap:28px;}#insurance-mobile-prototype .board-label{font-size:17px;font-weight:600;margin-bottom:12px;}</style>'
            page.set_viewport_size({'width':72+cols*390+(cols-1)*28,'height':1100})
            page.set_content(wrapper(html))
            page.screenshot(path=str(ROOT/filename),full_page=True)
        assert not errors, errors
        report={'result':'PASS','checks':checks,'page_errors':errors,'screens':len(SCREENS),'screenshots':[b[0] for b in boards]}
        (ROOT/'验证结果.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        print(json.dumps(report,ensure_ascii=False,indent=2))
        browser.close()

if __name__=='__main__':
    main()
