Attribute VB_Name = "modScheduling"
Option Explicit

' Column map: A=mat B=contract C=contract2 D=order E=product F=size G=p H=mult
' I=orderDate J=deadline K=cases L=pieces M=remain N-BQ=daily(56d)

Public Sub StartScheduling()
    Dim ws As Worksheet
    Set ws = ActiveSheet

    Dim orderRow As Long, dayCol As Long, scanRow As Long
    Const FIRST_ORDER_ROW As Long = 7
    Const LAST_SCAN_ROW As Long = 200
    Const FIRST_DAY_COL As Long = 14    ' Column N
    Const LAST_DAY_COL As Long = 69     ' Column BQ
    Const COL_SIZE As Long = 6          ' F = size for changeover
    Const COL_P As Long = 7             ' G = p value
    Const COL_MULT As Long = 8          ' H = multiplier
    Const COL_CASES As Long = 11        ' K = cases ordered
    Const COL_REMAIN As Long = 13       ' M = remaining to schedule
    Const MIN_BATCH As Long = 3         ' Minimum cases to run a product on a day

    Dim totalCases As Long, allocatedCases As Long, remainingCases As Long
    Dim baseCapacity As Long, availableCapacity As Long
    Dim pValue As Long, multiplier As Long, piecesPerCase As Long
    Dim maxCases As Long, allocate As Long
    Dim currentValue As Variant, currentSize As Variant
    Dim lossPerChange As Long, changeoverPenalty As Long
    Dim ordersProcessed As Long, ordersScheduled As Long
    Dim alreadyAllocatedPieces As Long
    Dim sumRow As Long, sumP As Long, sumMlt As Long, dayCases As Long
    Dim k As Long, found As Boolean
    Dim sizesToday() As String
    Dim sizeCount As Long
    Dim sizeVal As String

    Dim wsConfig As Worksheet
    Set wsConfig = ThisWorkbook.Sheets(2)
    baseCapacity = CLng(Val(ws.Cells(2, 11).Value & ""))  ' K2 = double-shift

    capShuang = CLng(Val(ws.Cells(2, 11).Value & ""))   ' K2
    capDan = CLng(Val(ws.Cells(1, 11).Value & ""))       ' K1

    Application.ScreenUpdating = False

    For orderRow = FIRST_ORDER_ROW To LAST_SCAN_ROW
        If Trim(ws.Cells(orderRow, 1).Value & "") = "" Then GoTo NextOrder

        pValue = Val(ws.Cells(orderRow, COL_P).Value & "")
        multiplier = Val(ws.Cells(orderRow, COL_MULT).Value & "")
        totalCases = CLng(Val(ws.Cells(orderRow, COL_CASES).Value & ""))
        currentSize = Trim(ws.Cells(orderRow, COL_SIZE).Value & "")

        If totalCases <= 0 Then GoTo NextOrder
        If pValue <= 0 Or multiplier <= 0 Then GoTo NextOrder

        ' Already allocated
        allocatedCases = 0
        For dayCol = FIRST_DAY_COL To LAST_DAY_COL
            currentValue = ws.Cells(orderRow, dayCol).Value
            If Not IsEmpty(currentValue) And currentValue <> "" Then
                allocatedCases = allocatedCases + CLng(Val(currentValue & ""))
            End If
        Next dayCol

        remainingCases = totalCases - allocatedCases
        If remainingCases <= 0 Then
            ws.Cells(orderRow, COL_REMAIN).Value = 0
            GoTo NextOrder
        End If

        piecesPerCase = pValue * multiplier
        ordersProcessed = ordersProcessed + 1

        ' Allocate day by day
        For dayCol = FIRST_DAY_COL To LAST_DAY_COL
            If remainingCases <= 0 Then Exit For

            ' Rest day or get shift capacity
            shiftText = Trim(ws.Cells(2, dayCol).Value & "")
            If shiftText = "" Then GoTo NextDay
            If InStr(1, shiftText, ChrW(21452)) > 0 Then
                baseCapacity = capShuang
            ElseIf InStr(1, shiftText, ChrW(21333)) > 0 Then
                baseCapacity = capDan
            Else
                GoTo NextDay
            End If

            ' Sum already allocated pieces today
            alreadyAllocatedPieces = 0
            For sumRow = FIRST_ORDER_ROW To LAST_SCAN_ROW
                If Trim(ws.Cells(sumRow, 1).Value & "") = "" Then GoTo NextSumRow
                currentValue = ws.Cells(sumRow, dayCol).Value
                If Not IsEmpty(currentValue) And currentValue <> "" Then
                    dayCases = CLng(Val(currentValue & ""))
                    If dayCases > 0 Then
                        sumP = Val(ws.Cells(sumRow, COL_P).Value & "")
                        sumMlt = Val(ws.Cells(sumRow, COL_MULT).Value & "")
                        alreadyAllocatedPieces = alreadyAllocatedPieces + dayCases * sumP * sumMlt
                    End If
                End If
NextSumRow:
            Next sumRow

            ' Get changeover loss from config
            lossPerChange = GetConfigValue(wsConfig, ws.Cells(1, 1).Value)

            ' Count distinct sizes today (including current order)
            sizeCount = 0
            ReDim sizesToday(0 To 200)

            For scanRow = FIRST_ORDER_ROW To LAST_SCAN_ROW
                If Trim(ws.Cells(scanRow, 1).Value & "") = "" Then GoTo NextSizeRow
                If scanRow = orderRow Then
                    sizeVal = currentSize
                Else
                    currentValue = ws.Cells(scanRow, dayCol).Value
                    If IsEmpty(currentValue) Or currentValue = "" Then GoTo NextSizeRow
                    If CLng(Val(currentValue & "")) <= 0 Then GoTo NextSizeRow
                    sizeVal = Trim(ws.Cells(scanRow, COL_SIZE).Value & "")
                End If

                If sizeVal = "" Then GoTo NextSizeRow

                found = False
                For k = 0 To sizeCount - 1
                    If sizesToday(k) = sizeVal Then
                        found = True
                        Exit For
                    End If
                Next k
                If Not found Then
                    sizesToday(sizeCount) = sizeVal
                    sizeCount = sizeCount + 1
                End If
NextSizeRow:
            Next scanRow

            ' Changeover penalty
            If sizeCount <= 1 Then
                changeoverPenalty = 0
            Else
                changeoverPenalty = (sizeCount - 1) * lossPerChange
            End If

            ' Available capacity
            availableCapacity = baseCapacity - alreadyAllocatedPieces - changeoverPenalty
            If availableCapacity <= 0 Then GoTo NextDay

            ' If net capacity after changeover is less than one changeover cycle, not worth switching
            If changeoverPenalty > 0 And availableCapacity < lossPerChange Then GoTo NextDay

            maxCases = availableCapacity \ piecesPerCase
            If maxCases <= 0 Then GoTo NextDay

            ' Skip tiny batches: if maxCases < MIN_BATCH and order continues beyond today
            If maxCases < MIN_BATCH And remainingCases > maxCases Then GoTo NextDay

            If maxCases > remainingCases Then
                allocate = remainingCases
            Else
                allocate = maxCases
            End If

            currentValue = ws.Cells(orderRow, dayCol).Value
            If IsEmpty(currentValue) Or currentValue = "" Then
                ws.Cells(orderRow, dayCol).Value = allocate
            Else
                ws.Cells(orderRow, dayCol).Value = CLng(Val(currentValue & "")) + allocate
            End If

            remainingCases = remainingCases - allocate
            ws.Cells(orderRow, COL_REMAIN).Value = remainingCases

NextDay:
        Next dayCol

        If remainingCases <= 0 Then
            ordersScheduled = ordersScheduled + 1
        End If

NextOrder:
    Next orderRow

    Application.ScreenUpdating = True

    Dim msg As String
    msg = GetPrompt("msg_sched_complete") & vbCrLf & vbCrLf & _
          GetPrompt("msg_processed") & ordersProcessed & vbCrLf & _
          GetPrompt("msg_scheduled") & ordersScheduled
    If ordersProcessed > ordersScheduled Then
        msg = msg & vbCrLf & GetPrompt("msg_shortfall2") & (ordersProcessed - ordersScheduled)
    End If
    MsgBox msg, vbInformation, GetPrompt("title_scheduling")
End Sub

'====================================================
' FlexScheduling - Select date range + starting product
'====================================================
Public Sub FlexScheduling()
    Dim ws As Worksheet
    Set ws = ActiveSheet

    ' --- Select date range by clicking cells ---
    Dim startRng As Range, endRng As Range, prodRng As Range
    Dim startCol As Long, endCol As Long
    Dim startOrderRow As Long

    On Error Resume Next
    Set startRng = Application.InputBox(GetPrompt("msg_start_date"), GetPrompt("title_start"), "N4", Type:=8)
    On Error GoTo 0
    If startRng Is Nothing Then Exit Sub
    If startRng.Row <> 4 Then
        MsgBox GetPrompt("msg_row4_err"), vbExclamation, GetPrompt("title_error")
        Exit Sub
    End If
    startCol = startRng.Column

    On Error Resume Next
    Set endRng = Application.InputBox(GetPrompt("msg_end_date"), GetPrompt("title_end"), Cells(4, startCol).Address, Type:=8)
    On Error GoTo 0
    If endRng Is Nothing Then Exit Sub
    If endRng.Row <> 4 Then
        MsgBox GetPrompt("msg_row4_err"), vbExclamation, GetPrompt("title_error")
        Exit Sub
    End If
    endCol = endRng.Column

    If endCol < startCol Then
        MsgBox GetPrompt("msg_date_order_err"), vbCritical, GetPrompt("title_error")
        Exit Sub
    End If

    On Error Resume Next
    Set prodRng = Application.InputBox(GetPrompt("msg_start_product"), GetPrompt("title_product"), "E7", Type:=8)
    On Error GoTo 0
    If prodRng Is Nothing Then Exit Sub
    If prodRng.Column <> 5 Then
        MsgBox GetPrompt("msg_colE_err"), vbExclamation, GetPrompt("title_error")
        Exit Sub
    End If
    If prodRng.Row < 7 Then
        MsgBox GetPrompt("msg_row7_err"), vbExclamation, GetPrompt("title_error")
        Exit Sub
    End If
    startOrderRow = prodRng.Row

    ' --- Run scheduling ---
    Dim orderRow As Long, dayCol As Long, scanRow As Long
    Dim totalCases As Long, allocatedCases As Long, remainingCases As Long
    Dim baseCapacity As Long, availableCapacity As Long
    Dim pValue As Long, multiplier As Long, piecesPerCase As Long
    Dim maxCases As Long, allocate As Long
    Dim currentValue As Variant, currentSize As Variant
    Dim lossPerChange As Long, changeoverPenalty As Long
    Dim ordersProcessed As Long, ordersScheduled As Long
    Dim alreadyAllocatedPieces As Long
    Dim sumRow As Long, sumP As Long, sumMlt As Long, dayCases As Long
    Dim k As Long, found As Boolean
    Dim sizesToday() As String
    Dim sizeCount As Long
    Dim sizeVal As String
    Const LAST_SCAN_ROW As Long = 200
    Const COL_SIZE As Long = 6
    Const COL_P As Long = 7
    Const COL_MULT As Long = 8
    Const COL_CASES As Long = 11
    Const COL_REMAIN As Long = 13
    Const MIN_BATCH As Long = 3

    Dim wsConfig As Worksheet
    Set wsConfig = ThisWorkbook.Sheets(2)

    Dim fCapShuang As Long, fCapDan As Long
    Dim fShiftText As String
    fCapShuang = CLng(Val(ws.Cells(2, 11).Value & ""))
    fCapDan = CLng(Val(ws.Cells(1, 11).Value & ""))

    Application.ScreenUpdating = False

    For orderRow = startOrderRow To LAST_SCAN_ROW
        If Trim(ws.Cells(orderRow, 1).Value & "") = "" Then GoTo NextFlexOrder

        pValue = Val(ws.Cells(orderRow, COL_P).Value & "")
        multiplier = Val(ws.Cells(orderRow, COL_MULT).Value & "")
        totalCases = CLng(Val(ws.Cells(orderRow, COL_CASES).Value & ""))
        currentSize = Trim(ws.Cells(orderRow, COL_SIZE).Value & "")

        If totalCases <= 0 Then GoTo NextFlexOrder
        If pValue <= 0 Or multiplier <= 0 Then GoTo NextFlexOrder

        allocatedCases = 0
        For dayCol = startCol To endCol
            currentValue = ws.Cells(orderRow, dayCol).Value
            If Not IsEmpty(currentValue) And currentValue <> "" Then
                allocatedCases = allocatedCases + CLng(Val(currentValue & ""))
            End If
        Next dayCol

        remainingCases = totalCases - allocatedCases
        If remainingCases <= 0 Then
            ws.Cells(orderRow, COL_REMAIN).Value = 0
            GoTo NextFlexOrder
        End If

        piecesPerCase = pValue * multiplier
        ordersProcessed = ordersProcessed + 1

        For dayCol = startCol To endCol
            If remainingCases <= 0 Then Exit For

            fShiftText = Trim(ws.Cells(2, dayCol).Value & "")
            If fShiftText = "" Then GoTo NextFlexDay
            If InStr(1, fShiftText, ChrW(21452)) > 0 Then
                baseCapacity = fCapShuang
            ElseIf InStr(1, fShiftText, ChrW(21333)) > 0 Then
                baseCapacity = fCapDan
            Else
                GoTo NextFlexDay
            End If

            alreadyAllocatedPieces = 0
            For sumRow = 7 To LAST_SCAN_ROW
                If Trim(ws.Cells(sumRow, 1).Value & "") = "" Then GoTo NextFlexSum
                currentValue = ws.Cells(sumRow, dayCol).Value
                If Not IsEmpty(currentValue) And currentValue <> "" Then
                    dayCases = CLng(Val(currentValue & ""))
                    If dayCases > 0 Then
                        sumP = Val(ws.Cells(sumRow, COL_P).Value & "")
                        sumMlt = Val(ws.Cells(sumRow, COL_MULT).Value & "")
                        alreadyAllocatedPieces = alreadyAllocatedPieces + dayCases * sumP * sumMlt
                    End If
                End If
NextFlexSum:
            Next sumRow

            lossPerChange = GetConfigValue(wsConfig, ws.Cells(1, 1).Value)

            sizeCount = 0
            ReDim sizesToday(0 To 200)
            For scanRow = 7 To LAST_SCAN_ROW
                If Trim(ws.Cells(scanRow, 1).Value & "") = "" Then GoTo NextFlexSize
                If scanRow = orderRow Then
                    sizeVal = currentSize
                Else
                    currentValue = ws.Cells(scanRow, dayCol).Value
                    If IsEmpty(currentValue) Or currentValue = "" Then GoTo NextFlexSize
                    If CLng(Val(currentValue & "")) <= 0 Then GoTo NextFlexSize
                    sizeVal = Trim(ws.Cells(scanRow, COL_SIZE).Value & "")
                End If
                If sizeVal = "" Then GoTo NextFlexSize
                found = False
                For k = 0 To sizeCount - 1
                    If sizesToday(k) = sizeVal Then
                        found = True
                        Exit For
                    End If
                Next k
                If Not found Then
                    sizesToday(sizeCount) = sizeVal
                    sizeCount = sizeCount + 1
                End If
NextFlexSize:
            Next scanRow

            If sizeCount <= 1 Then
                changeoverPenalty = 0
            Else
                changeoverPenalty = (sizeCount - 1) * lossPerChange
            End If

            availableCapacity = baseCapacity - alreadyAllocatedPieces - changeoverPenalty
            If availableCapacity <= 0 Then GoTo NextFlexDay

            If changeoverPenalty > 0 And availableCapacity < lossPerChange Then GoTo NextFlexDay

            maxCases = availableCapacity \ piecesPerCase
            If maxCases <= 0 Then GoTo NextFlexDay
            If maxCases < MIN_BATCH And remainingCases > maxCases Then GoTo NextFlexDay

            If maxCases > remainingCases Then
                allocate = remainingCases
            Else
                allocate = maxCases
            End If

            currentValue = ws.Cells(orderRow, dayCol).Value
            If IsEmpty(currentValue) Or currentValue = "" Then
                ws.Cells(orderRow, dayCol).Value = allocate
            Else
                ws.Cells(orderRow, dayCol).Value = CLng(Val(currentValue & "")) + allocate
            End If

            remainingCases = remainingCases - allocate
            ws.Cells(orderRow, COL_REMAIN).Value = remainingCases

NextFlexDay:
        Next dayCol

        If remainingCases <= 0 Then
            ordersScheduled = ordersScheduled + 1
        End If

NextFlexOrder:
    Next orderRow

    Application.ScreenUpdating = True

    Dim fmsg As String
    fmsg = GetPrompt("msg_done") & vbCrLf & vbCrLf & _
           GetPrompt("msg_date_range") & Format(ws.Cells(4, startCol).Value, "YYYY-MM-DD") & _
           GetPrompt("msg_to") & Format(ws.Cells(4, endCol).Value, "YYYY-MM-DD") & vbCrLf & _
           GetPrompt("msg_start_row") & startOrderRow & vbCrLf & vbCrLf & _
           GetPrompt("msg_processed") & ordersProcessed & vbCrLf & _
           GetPrompt("msg_scheduled") & ordersScheduled
    If ordersProcessed > ordersScheduled Then
        fmsg = fmsg & vbCrLf & GetPrompt("msg_shortfall2") & (ordersProcessed - ordersScheduled)
    End If
    MsgBox fmsg, vbInformation, GetPrompt("msg_sched_complete")
End Sub


' Read Chinese prompt string from 提示框文本 sheet (avoids encoding issues in VBA source)
Private Function GetPrompt(key As String) As String
    Dim r As Long
    For r = 1 To 32
        If Trim(ThisWorkbook.Sheets("提示框文本").Cells(r, 1).Value & "") = key Then
            GetPrompt = Trim(ThisWorkbook.Sheets("提示框文本").Cells(r, 2).Value & "")
            Exit Function
        End If
    Next r
    GetPrompt = key  ' Fallback: return key itself
End Function

Private Function GetConfigValue(wsConfig As Worksheet, lineName As Variant) As Long
    Dim r As Long
    For r = 2 To 100
        If Trim(wsConfig.Cells(r, 1).Value & "") = Trim(lineName & "") Then
            GetConfigValue = CLng(Val(wsConfig.Cells(r, 2).Value & ""))
            Exit Function
        End If
    Next r
    GetConfigValue = 0
End Function

Public Sub ClearScheduling()
    Dim ws As Worksheet
    Set ws = ActiveSheet

    Dim orderRow As Long, dayCol As Long
    Const FIRST_ORDER_ROW As Long = 7
    Const LAST_SCAN_ROW As Long = 200
    Const FIRST_DAY_COL As Long = 14
    Const LAST_DAY_COL As Long = 69
    Const COL_REMAIN As Long = 13

    Dim totalOrders As Long

    totalOrders = 0
    For orderRow = FIRST_ORDER_ROW To LAST_SCAN_ROW
        If Trim(ws.Cells(orderRow, 1).Value & "") <> "" Then
            totalOrders = totalOrders + 1
        End If
    Next orderRow

    If totalOrders = 0 Then
        MsgBox GetPrompt("msg_no_orders"), vbExclamation, GetPrompt("title_clear")
        Exit Sub
    End If

    If MsgBox(GetPrompt("msg_clear_confirm1") & ws.Name & GetPrompt("msg_clear_confirm2") & vbCrLf & vbCrLf & _
              GetPrompt("msg_clear_confirm3") & totalOrders & GetPrompt("msg_clear_confirm4"), _
              vbYesNo + vbQuestion, GetPrompt("title_clear")) = vbNo Then
        Exit Sub
    End If

    Application.ScreenUpdating = False

    Dim cleared As Long
    cleared = 0

    For orderRow = FIRST_ORDER_ROW To LAST_SCAN_ROW
        If Trim(ws.Cells(orderRow, 1).Value & "") = "" Then GoTo NextOrderClr

        For dayCol = FIRST_DAY_COL To LAST_DAY_COL
            ws.Cells(orderRow, dayCol).Value = ""
        Next dayCol

        ws.Cells(orderRow, COL_REMAIN).Value = 0
        cleared = cleared + 1

NextOrderClr:
    Next orderRow

    Application.ScreenUpdating = True

    MsgBox GetPrompt("msg_cleared1") & cleared & GetPrompt("msg_cleared2"), _
           vbInformation, GetPrompt("title_clear")
End Sub
