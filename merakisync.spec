# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src/merakisync/cli/cli.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        # Migration scripts and the Mako template must be on disk at runtime
        # so Alembic can discover and execute them.  They are extracted to
        # {sys._MEIPASS}/merakisync/migrations/ by the bootloader.
        ('src/merakisync/migrations', 'merakisync/migrations'),
    ],
    hiddenimports=[
        # SQLAlchemy loads the psycopg2 dialect from a string ("postgresql+psycopg2")
        # at engine-creation time — the static import graph never touches it.
        'sqlalchemy.dialects.postgresql',
        'sqlalchemy.dialects.postgresql.psycopg2',

        # psycopg2: the C extension is auto-detected as a binary but listing
        # the module names ensures the Python shim is included too.
        'psycopg2',
        'psycopg2._psycopg',
        'psycopg2.extensions',
        'psycopg2.extras',

        # Alembic internals loaded dynamically during migrate.
        'alembic.runtime.migration',
        'alembic.operations',
        'alembic.operations.ops',
        'alembic.operations.toimpl',
        'alembic.script.revision',
        'alembic.ddl',
        'alembic.ddl.postgresql',

        # Mako is Alembic's template engine for script.py.mako.
        'mako',
        'mako.template',
        'mako.lookup',
        'mako.runtime',
        'mako.filters',
        'mako.cache',
        'mako.codegen',
        'mako.compat',

        # identify-ip: RDAP-based IP registrant lookup used during uplink sync.
        'identify_ip',

        # Meraki SDK — list top-level package so all submodules are traced.
        'meraki',
        'meraki.api',

        # merakisync migration modules: Alembic discovers them from disk (via
        # datas above), but listing them here ensures they are also compiled
        # into the bundle so imports work regardless of extraction state.
        'merakisync.migrations',
        'merakisync.migrations.env',
        'merakisync.migrations.versions',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='merakisync',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
