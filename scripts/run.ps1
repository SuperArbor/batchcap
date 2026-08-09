# ============================
# Sort Pipeline output
# ============================

function GetAnsVal {
param(
    [Parameter(Mandatory=$true, ValueFromPipeline=$true)]
    [System.Object[]]
    [AllowEmptyString()]
    $Output
)

    $all = New-Object System.Collections.Generic.List[System.Object]
    $exception = New-Object System.Collections.Generic.List[System.Object]
    $stderr = New-Object System.Collections.Generic.List[System.Object]
    $stdout = New-Object System.Collections.Generic.List[System.Object]

    $Output | ForEach-Object {

        if ($_ -ne $null) {

            if ($_.GetType().FullName -ne 'System.Management.Automation.ErrorRecord') {

                if ($null -ne $_.Exception.message) {
                    $all.Add($_.Exception.message)
                    $exception.Add($_.Exception.message)
                }
                else {
                    $stdout.Add($_)
                }

            }
            else {
                $all.Add($_.Exception.message)
                $stderr.Add($_.Exception.message)
            }

        }
    }

    [hashtable]$return = @{}

    $return.Meta0 = $all
    $return.Meta1 = $exception
    $return.Meta2 = $stderr
    $return.Meta3 = $stdout

    return $return
}

# Replace '\r\n' with '\n'
function Replace {
param(
    [Parameter(Mandatory=$true, ValueFromPipeline=$true)]
    [hashtable]$r
)

    $Meta0 = ""

    foreach ($el in $r.Meta0) {
        $Meta0 += $el
    }

    $Meta0 = ($Meta0 -split "[`r`n]") -join "`n"
    $Meta0 = ($Meta0 -split "[`n]{2,}") -join "`n"

    return $Meta0
}

# ============================
# Run BatchCap
# ============================

& batchcap `
    -p $PSScriptRoot `
    -s 1 `
    -i `
    -c yellow `
    -n 0.08 `
    -g 270 `
    -r 0.01 `
    -t 4x4 `
    -o `
    -f png `
    2>&1 |
    ForEach-Object {
        & GetAnsVal $_ | & Replace
    }
