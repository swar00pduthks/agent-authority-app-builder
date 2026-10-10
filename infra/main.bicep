// One-command install into the customer's own Azure tenant (skeleton).
// Creates the platform's own resources; the Entra app registration and role assignments
// (Authority.Read / Ingest / Content / Admin) are created by the install script.

@description('Short environment name, e.g. pilot1')
param name string

@allowed([ 'dev', 'test', 'staging', 'prod' ])
param environment string = 'prod'

param location string = resourceGroup().location

@description('Optional branding seeded through Agent Authority\'s branding API as a governance run under the installer\'s identity. If the accent fails 4.5:1 contrast, defaults are kept.')
param productName string = ''
param logoUrl string = ''
param accent string = ''

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${name}'
  location: location
  properties: { retentionInDays: 90, sku: { name: 'PerGB2018' } }
}

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-${name}'
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enablePurgeProtection: true
    publicNetworkAccess: 'Disabled'
  }
}

resource apps 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${name}'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

output environmentName string = environment
output brandingSeed object = { productName: productName, logoUrl: logoUrl, accent: accent }
