// tests/.passie/outerlands.test.js
'use strict'

module.exports = function (info) {
    const cfg = info.require('adapters/outerlands-masha.js')

    info.register('should register outerlands module', () => {
        info.require('masha-files/test-outerlands.masha')
        info.require('helpers/outerlands-module.py')

        if (cfg.output === undefined) throw new Error(
            'Nakurity Lang failed at the language level, see error above ^^'
        )

        if (!cfg.ok) throw new Error(
            'Nakurity Lang did not run outerlands module'
        )
    })
}