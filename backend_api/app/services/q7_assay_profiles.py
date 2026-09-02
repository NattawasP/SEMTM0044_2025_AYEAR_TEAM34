ASSAY_PROFILES = {
    'adherent_screen': {
        'name': 'Adherent screen',
        'need_growth': ['2D: adherent'],
        'description': 'Standard drug screens on flat plates',
    },

    '3d_spheroid': {
        'name': '3D spheroid',
        'need_growth': ['2D: adherent'],
        'description': 'Adherent cells that form spheroids',
    },

    'suspension_screen': {
        'name': 'Suspension screen',
        'need_growth': ['2D: suspension'],
        'description': 'For blood/lymphoid cells',
    },

    'flexible': {
        'name': 'Flexible culture',
        'need_growth': ['2D: adherent', '2D: suspension', '2D: mixed adherent and suspension'],
        'description': 'Any growth type is fine',
    },
}
