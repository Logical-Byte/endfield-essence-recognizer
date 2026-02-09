import prettier from 'eslint-config-prettier/flat'
import vuetify from 'eslint-config-vuetify'

export default vuetify(prettier, {
  rules: {
    'unicorn/prefer-ternary': 'off',
    'unicorn/no-negated-condition': 'off',
    '@typescript-eslint/no-inferrable-types': 'off',
  },
})
